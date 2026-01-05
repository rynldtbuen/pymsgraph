from typing import TYPE_CHECKING, Any

from pymsgraph.fields import CharField, Field

if TYPE_CHECKING:
    from pymsgraph.client import Client
    from pymsgraph.query import QuerySet, TModel


class Model:
    FIELDS: dict[str, Field]
    REQUIRED_FIELDS: frozenset[str]

    id = CharField()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        fields: dict[str, Field] = {}
        required_fields: set[str] = set()

        for base in cls.__mro__[1:]:
            base_fields = getattr(base, "FIELDS", None)
            if base_fields:
                fields.update(base_fields)
        for name, attr in cls.__dict__.items():
            if isinstance(attr, Field):
                fields[name] = attr
                if attr.required:
                    required_fields.add(name)

        cls.FIELDS = fields
        cls.REQUIRED_FIELDS = frozenset(required_fields)

    def __init__(
        self,
        parent_obj: "QuerySet[TModel] | Model | None" = None,
        **kwargs: Any,
    ) -> None:
        self._data: dict[str, Any] = {}
        self._graph_data: dict[str, Any] = {}
        self._dirty: set[str] = set()
        self._parent_obj = parent_obj

        self._initializing = True
        for k, v in kwargs.items():
            setattr(self, k, v)
        self._initializing = False

    def to_graph(self, *, for_update: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if for_update:
            names = self._dirty
        else:
            names = self._data.keys()

        for name in names:
            field = self.FIELDS.get(name)
            if field is None or field.read_only:
                continue
            val = self._data.get(name, field.default)
            if val is None:
                continue
            graph_attr_name = field.graph_attr_name or name
            payload[graph_attr_name] = field.to_graph(val)

        return payload

    @classmethod
    def from_graph(cls, data: dict[str, Any]):
        obj = cls()
        obj._initializing = True

        for name, field in cls.FIELDS.items():
            if (graph_attr_name := field.graph_attr_name) is not None:
                val = data.get(graph_attr_name)
                if val is not None or field.required:
                    setattr(obj, name, val)
            else:
                raise ValueError(
                    f"Field should defined a Graph attribute name, '{name}'"
                )

        obj._graph_data = data
        obj._initializing = False
        return obj

    @property
    def _endpoint(self) -> str:
        if self._parent_obj is None:
            raise RuntimeError("parent_obj has not been initialized.")
        if self.id is None:
            raise RuntimeError("object has not been initialized or does not exist.")
        return f"{self._parent_obj._endpoint}/{self.id}"

    @property
    def _client(self) -> "Client":
        if self._parent_obj is None:
            raise RuntimeError("parent_obj has not been initialized.")
        return self._parent_obj._client

    def _validate_required_fields(self) -> None:
        missing: list[str] = []
        for name in self.REQUIRED_FIELDS:
            if field := self.FIELDS.get(name):
                val = self._data.get(name, field.default)
                if val is None or val == "":
                    missing.append(name)
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
