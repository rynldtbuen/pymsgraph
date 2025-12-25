from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from pymsgraph.fields import CharField, Field


if TYPE_CHECKING:
    from pymsgraph.client import Client
    from pymsgraph.query import QuerySet

TModel = TypeVar("TModel", bound="Model")


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


class EndpointDescriptor:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def __get__(self, obj, objtype=None) -> str:
        if obj is None:
            return self.endpoint
        if not obj.id:
            raise ValueError(
                f"Resource {type(obj)} has not been initialized or does not exist"
            )
        return f"{self.endpoint}/{obj.id}"


class Model(metaclass=ModelBase):
    """
    Base model for Graph resources
    """

    _meta: ClassVar[Meta]
    is_read_only: ClassVar[bool] = False

    endpoint: EndpointDescriptor
    id = CharField(read_only=True)

    def __init__(
        self,
        *,
        qs: QuerySet | None = None,
        graph_data: dict[str, Any] | None = None,
        **kwargs,
    ):
        self._initializing = True
        self._qs = qs
        self._data: dict[str, Any] = {}
        self._graph_data = graph_data or {}
        self._dirty: set[str] = set()

        # apply defaults
        for name, f in self._meta.fields.items():
            if f.default is not None and name not in kwargs:
                self._data[name] = f.default

        # graph_data wins over kwargs
        # hydrate from graph data via descriptors (still _initializing)
        if graph_data:
            for gname, value in graph_data.items():
                field = self._meta.fields_by_graph.get(gname)
                if field:
                    setattr(self, field.name, value)
        else:
            # apply kwargs via descriptors (dirty suppressed because _initializing)
            for k, v in kwargs.items():
                setattr(self, k, v)

        self._dirty.clear()
        self._initializing = False

    # @property
    # def endpoint(self) -> str:
    #     if self.id is None:
    #         raise ValueError("Resource has not been initialized or does not exist")
    #     qs_endpoint = self._qs._endpoint if self._qs else None
    #     if qs_endpoint:
    #         return f"{qs_endpoint}/{self.id}"
    #     raise ValueError("QuerySet endpoint is not configured for this model instance")

    @property
    def client(self) -> Client:
        if self._qs is None:
            raise ValueError("QuerySet is not configured for this model instance")
        return self._qs._client

    def to_graph(self, *, for_update: bool) -> dict[str, Any]:  # type: ignore
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

    def save(self) -> bool:
        if self.is_read_only:
            raise RuntimeError(f"Model '{self.__class__.__name__}' is read-only.")

        if self.id is None:
            raise RuntimeError(
                "Cannot save a model that has not been initialized or created yet."
            )

        payload = self.to_graph(for_update=True)
        if not payload:
            return False

        self.client.patch(self.endpoint, json_body=payload)
        self._dirty.clear()
        return True

    def delete(self, *, force: bool = False) -> None:
        if self.is_read_only:
            raise RuntimeError(f"Model '{self.__class__.__name__}' is read-only.")
        if not force:
            raise RuntimeError(
                "Refusing to delete User without confirmation. "
                "Call delete(force=True) to proceed."
            )

        self.client.delete(self.endpoint)

        # Local cleanup (object represents a deleted remote resource)
        self._data.clear()
        self._dirty.clear()

    def refresh_from_graph(self, data: dict[str, Any]) -> None:
        # Rehydrate using graph data without marking fields dirty.
        self._data = self.__class__(graph_data=data, qs=self._qs)._data
        self._dirty.clear()
        self._graph_data = data

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
