from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Self, TypeVar

from pymsgraph.fields import Field
from pymsgraph.manager import GraphManager


if TYPE_CHECKING:
    from pymsgraph.manager import GraphManager
    from pymsgraph.client import GraphClient

TModel = TypeVar("TModel", bound="GraphModel")
TManager = TypeVar("TManager", bound="GraphManager")


@dataclass(frozen=True)
class Capabilities:
    filter: bool = True
    search: bool = False
    order_by: bool = True
    # implement later
    # select_related: bool = False


@dataclass(frozen=True)
class ModelOptions:
    """Django-ish _meta container."""

    fields: dict[str, Field]  # python_name -> Field
    fields_by_graph: dict[str, Field]  # graph_name -> Field

    def field_to_graph(self, py_field: str) -> str:
        try:
            f = self.fields[py_field]
        except KeyError:
            raise ValueError(f"Unknown field: {py_field!r}")
        assert f.graph_name is not None
        return f.graph_name


class GraphModelBase(type):
    """Collect Field descriptors and bind managers."""

    def __new__(mcls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]):
        # inherit fields from bases
        fields: dict[str, Field] = {}
        for b in bases:
            meta: ModelOptions | None = getattr(b, "_meta", None)
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

        setattr(cls, "_meta", ModelOptions(fields=fields, fields_by_graph=by_graph))

        # Bind objects manager if present; otherwise attach a default manager.
        objects = attrs.get("objects")
        if objects is None:
            objects = GraphManager(cls)
            setattr(cls, "objects", objects)  # type: ignore
        objects.contribute_to_model(cls)

        capabilities = attrs.get("capabilities")
        if capabilities is None:
            setattr(cls, "capabilities", Capabilities())

        return cls


class GraphModel(metaclass=GraphModelBase):
    """Base model for Graph resources.

    Expected client interface:
      client.get(path, params=None) -> dict
      client.post(path, json_body=None) -> dict
      client.patch(path, json_body=None) -> Any
      client.delete(path) -> Any
    """

    endpoint: ClassVar[str] = ""
    objects: ClassVar[Any]  # set by GraphModelBase (default) or overridden on model
    capabilities: ClassVar[Capabilities]
    _meta: ClassVar[ModelOptions]  # populated by GraphModelBase

    # shared client (simple start)
    _default_client: ClassVar["GraphClient | None"] = None
    _client: ClassVar["GraphClient | None"] = None  # per-modsel override

    # common id field
    id = Field(read_only=True)

    def __init__(self, **kwargs: Any) -> None:
        self._data: dict[str, Any] = {}
        self._dirty: set[str] = set()
        self._initializing = True
        self._graph_payload: dict[str, Any] = {}

        # apply defaults
        for fname, f in self._meta.fields.items():
            if f.default is not None and fname not in kwargs:
                self._data[fname] = f.default

        for k, v in kwargs.items():
            setattr(self, k, v)

        self._initializing = False

    @classmethod
    def configure(cls, client: "GraphClient") -> None:
        cls._client = client

    @classmethod
    def configure_default(cls, client: "GraphClient") -> None:
        # global/default binding (call once)
        GraphModel._default_client = client

    @classmethod
    def _get_client(cls) -> "GraphClient":
        c = cls._client or cls._default_client
        if not c:
            raise RuntimeError(
                "Graph client not configured. Call graph.configure_default() or Model.configure()."
            )
        return c

    @classmethod
    def from_graph(cls: type[TModel], payload: dict[str, Any]) -> TModel:
        obj = cls()  # type: ignore[call-arg]
        obj._initializing = True

        for gname, value in payload.items():
            field = cls._meta.fields_by_graph.get(gname)
            if not field:
                continue
            obj._data[field.name] = field.to_python(value)

        obj._dirty.clear()
        obj._graph_payload = payload
        obj._initializing = False
        return obj

    def get_endpoint(self) -> str:
        if self.id:
            return f"{self.endpoint}/{self.get_id()}"
        return self.endpoint

    def get_id(self):
        val = self.id
        if not val:
            raise ValueError("model is not initialized or does not exist.")
        return val

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

    def save(self) -> None:
        client = self.__class__._get_client()

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
        self.__class__._get_client().delete(f"{self.endpoint}/{self.id}")

    def refresh_from_graph(self, payload: dict[str, Any]) -> Self:
        hydrated = self.__class__.from_graph(payload)
        self._data = hydrated._data
        self._dirty.clear()
        self._graph_payload = payload
        return self
