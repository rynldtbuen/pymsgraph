from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from pymsgraph.fields import CharField, Field


if TYPE_CHECKING:
    from pymsgraph.client import Client

TModel = TypeVar("TModel", bound="Model")
TReadOnlyModel = TypeVar("TReadOnlyModel", bound="ReadOnlyModel")


@dataclass(frozen=True)
class Capabilities:
    filter: bool = True
    search: bool = False
    order_by: bool = True


@dataclass(frozen=True)
class Meta:
    fields: dict[str, Field]  # python_name -> Field
    fields_by_graph: dict[str, Field]  # graph_name -> Field

    def field_to_graph(self, py_field: str) -> str:
        try:
            f = self.fields[py_field]
        except KeyError:
            raise ValueError(f"Unknown field: {py_field!r}")
        assert f.graph_name is not None
        return f.graph_name


class ModelBase(type):
    """Metaclass thats collects Field descriptors from class definitions"""

    def __new__(mcls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]):
        # inherit fields from bases
        fields: dict[str, Field] = {}
        for b in bases:
            meta: Meta | None = getattr(b, "_meta", None)
            if meta:
                fields.update(meta.fields)

        # fields declared on this class
        for k, v in attrs.items():
            if isinstance(v, Field):
                fields[k] = v

        cls = super().__new__(mcls, name, bases, attrs)

        # build _meta (Field.__set_name__ has run by now)
        by_graph: dict[str, Field] = {}
        for f in fields.values():
            if f.graph_name:
                by_graph[f.graph_name] = f

        setattr(cls, "_meta", Meta(fields=fields, fields_by_graph=by_graph))

        return cls


class ReadOnlyModel(metaclass=ModelBase):
    """
    Base model for read-only Graph resources
    """

    _meta: ClassVar[Meta]

    def __init__(self, **kwargs: Any) -> None:
        self._data: dict[str, Any] = {}
        self._graph_payload: dict[str, Any] = {}

        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def from_graph(
        cls: type[TReadOnlyModel], payload: dict[str, Any]
    ) -> TReadOnlyModel:
        obj = cls()

        for gname, value in payload.items():
            field = cls._meta.fields_by_graph.get(gname)
            if not field:
                continue
            obj._data[field.name] = field.to_python(value)

        obj._graph_payload = payload
        return obj

    def to_graph(self) -> dict[str, Any]:
        out: dict[str, Any] = {}

        for py_name, field in self._meta.fields.items():
            val = self._data.get(py_name, field.default)
            if val is None:
                continue

            assert field.graph_name is not None
            out[field.graph_name] = field.to_graph(val)

        return out


class Model(metaclass=ModelBase):
    """
    Base model for Graph resources
    """

    _meta: ClassVar[Meta]

    # common id field
    id = CharField(read_only=True)

    def __init__(self, client: Client, *, base_endpoint: str, **kwargs: Any) -> None:
        self._client = client
        self._data: dict[str, Any] = {}
        self._dirty: set[str] = set()
        self._graph_payload: dict[str, Any] = {}
        self._base_endpoint = base_endpoint

        # apply defaults
        for fname, f in self._meta.fields.items():
            if f.default is not None and fname not in kwargs:
                self._data[fname] = f.default

        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def from_graph(cls: type[TModel], payload: dict[str, Any]) -> TModel:
        obj = cls()  # type: ignore[call-arg]

        for gname, value in payload.items():
            field = cls._meta.fields_by_graph.get(gname)
            if not field:
                continue
            obj._data[field.name] = field.to_python(value)

        obj._dirty.clear()
        obj._graph_payload = payload
        return obj

    @property
    def endpoint(self) -> str:
        if self.id is None:
            raise ValueError("Resource has not been initialized or does not exist")
        return f"{self._base_endpoint}/{self.id}"

    def to_graph(self, *, for_update: bool) -> dict[str, Any]:
        out: dict[str, Any] = {}

        for py_name, field in self._meta.fields.items():
            if field.read_only:
                continue
            if for_update and py_name not in self._dirty:
                continue

            val = self._data.get(py_name, field.default)
            if val is None:
                continue

            assert field.graph_name is not None
            out[field.graph_name] = field.to_graph(val)

        return out

    def save(self) -> None:
        client = self._client

        if getattr(self, "id") is None:
            self._validate_for_create()
            payload = self.to_graph(for_update=False)
            created = client.post(self.endpoint, json_body=payload)
            hydrated = self.__class__.from_graph(created)
            self._data = hydrated._data
            self._dirty.clear()
            return

        payload = self.to_graph(for_update=True)
        if not payload:
            return

        client.patch(f"{self.endpoint}/{self.id}", json_body=payload)
        self._dirty.clear()

    def delete(self) -> None:
        if getattr(self, "id") is None:
            return
        self._client.delete(f"{self.endpoint}/{self.id}")

    def refresh_from_graph(self, payload: dict[str, Any]) -> None:
        hydrated = self.__class__.from_graph(payload)
        self._data = hydrated._data
        self._dirty.clear()
        self._graph_payload = payload

    def _validate_for_create(self) -> None:
        missing: list[str] = []
        for py_name, field in self._meta.fields.items():
            if field.read_only:
                continue
            if field.required:
                val = getattr(self, py_name)
                if val in (None, ""):
                    missing.append(py_name)
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
