from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from pymsgraph.fields import CharField, Field, QuerySetField

if TYPE_CHECKING:
    from pymsgraph.models.base import Model
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


class EndpointDescriptor:
    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint

    def __get__(self, obj: "Model", objtype=None) -> str | None:
        if obj is None:
            return self.endpoint
        model_class_endpoint = self.endpoint
        relative_ep = obj._relative_endpoint or obj.id
        if relative_ep is None and obj._has_identity():
            raise ValueError(
                f"Resource {type(obj)} has not been initialized or does not exist"
            )
        if parent_ep := getattr(obj._parent, "endpoint", None):
            if not relative_ep:
                return f"{parent_ep}{model_class_endpoint}"
            return f"{parent_ep}/{relative_ep}"
        if model_class_endpoint:
            return f"{model_class_endpoint}/{relative_ep}"
        raise RuntimeError(f"No endpoint found.")


class ModelBase(type):
    """Metaclass thats collects Field descriptors from class definitions"""

    def __new__(mcls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]):
        # inherit fields from bases
        fields: dict[str, Field] = {}
        prefetch_fields: set[str] = set()
        for b in bases:
            meta: Meta | None = getattr(b, "_meta", None)
            if meta:
                fields.update(meta.fields)
            prefetch_fields.update(getattr(b, "prefetch_fields", set()))

        # fields declared on this class
        for k, v in attrs.items():
            if isinstance(v, QuerySetField):
                fields[k] = v
                if getattr(v, "is_prefetch", False):
                    prefetch_fields.add(k)

        cls = super().__new__(mcls, name, bases, attrs)

        # build _meta (Field.__set_name__ has run by now)
        by_graph: dict[str, Field] = {}
        for f in fields.values():
            if f.graph_name:
                by_graph[f.graph_name] = f

        setattr(cls, "_meta", Meta(fields=fields, fields_by_graph=by_graph))
        setattr(cls, "prefetch_fields", prefetch_fields)
        setattr(cls, "endpoint", EndpointDescriptor(attrs.get("endpoint")))

        return cls


class Model(metaclass=ModelBase):
    """
    Base model for Graph resources
    """

    _meta: ClassVar["Meta"]
    is_read_only: ClassVar[bool] = False

    endpoint: ClassVar[str]
    id = CharField(read_only=True)

    def __init__(
        self,
        *,
        graph_data: dict[str, Any] | None = None,
        parent: TModel | "QuerySet[TModel]" | None = None,
        **kwargs,
    ):
        self._initializing = True
        self._parent = parent
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

        self._client.patch(self.endpoint, json_body=payload)
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

        self._client.delete(self.endpoint)

        # Local cleanup (object represents a deleted remote resource)
        self._data.clear()
        self._dirty.clear()

    def refresh_from_graph(self, data: dict[str, Any]) -> None:
        # Rehydrate using graph data without marking fields dirty.
        self._data = self.__class__(graph_data=data, parent=self._parent)._data
        self._dirty.clear()
        self._graph_data = data

    def _has_identity(self) -> bool:
        return True

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

    @property
    def _client(self):
        if c := getattr(self._parent, "_client", None):
            return c
        raise RuntimeError("No client found.")

    @property
    def _relative_endpoint(self) -> str | None:
        return None
