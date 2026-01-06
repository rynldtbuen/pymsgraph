from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar

from pymsgraph.models.fields import CharField, Field
from pymsgraph.models.query import Context
from pymsgraph.utils import to_snake_case

if TYPE_CHECKING:
    from pymsgraph.models.query import QuerySet


__all__ = ["Model"]

_Tm = TypeVar("_Tm", bound="Model")


class Model(Generic[_Tm]):
    REQUIRED_FIELDS: frozenset[str]
    FIELD_NAME_MAP: dict[str, str]

    id = CharField()

    def __init_subclass__(cls: type[_Tm], **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        fields: dict[str, Field] = {}
        required_fields: set[str] = set()
        field_name_map: dict[str, str] = {}

        for base in cls.__mro__[1:]:
            base_fields = getattr(base, "FIELDS", None)
            if not base_fields:
                base_fields = {
                    name: attr
                    for name, attr in base.__dict__.items()
                    if isinstance(attr, Field)
                }
            if base_fields:
                fields.update(base_fields)
                for name, attr in base_fields.items():
                    if graph_attr_name := attr.graph_attr_name:
                        field_name_map[graph_attr_name] = name
                    if attr.required:
                        required_fields.add(name)

        for name, attr in cls.__dict__.items():
            if isinstance(attr, Field):
                fields[name] = attr
                if graph_attr_name := attr.graph_attr_name:
                    field_name_map[graph_attr_name] = name
                if attr.required:
                    required_fields.add(name)

        cls.FIELDS = fields
        cls.REQUIRED_FIELDS = frozenset(required_fields)
        cls.FIELD_NAME_MAP = field_name_map

    def __init__(
        self,
        context: "Context[_Tm] | None" = None,
        **kwargs: Any,
    ) -> None:
        self._data: dict[str, Any] = {}
        self._graph_data: dict[str, Any] = {}
        self._dirty: set[str] = set()
        self._ctx = context or Context[_Tm]()

        self._initializing = True
        for k, v in kwargs.items():
            setattr(self, k, v)
        self._initializing = False

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k, None) for k in self.FIELDS}

    def serialize(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        attr_names = self._dirty or self._data.keys()

        for attr_name in attr_names:
            field = self.FIELDS[attr_name]
            if field.read_only:
                continue
            try:
                val = self._data[attr_name]
            except KeyError:
                continue
            if gr_attr_name := field.graph_attr_name:
                data[gr_attr_name] = field.to_graph(val)

        return data

    async def save(self) -> bool:
        if self.id is None:
            self._validate_required_fields()
            ep = self._ctx.endpoint
            client_method = self._ctx.client.post
        else:
            ep = self._ctx.endpoint
            client_method = self._ctx.client.patch

        body = self.serialize()

        if not body:
            return False

        await client_method(ep, body=body)
        self._dirty.clear()
        return True

    @classmethod
    def from_graph(
        cls, data: dict[str, Any], context: Context[Any] | None = None
    ) -> Self:
        obj = cls(context=context)
        obj._initializing = True

        for graph_attr_name, val in data.items():
            py_attr_name = to_snake_case(graph_attr_name)
            if cls.FIELDS.get(py_attr_name):
                setattr(obj, py_attr_name, val)

        obj._graph_data = data
        obj._initializing = False
        return obj

    @property
    def _endpoint(self) -> str:
        return f"{self._ctx.endpoint}/{self.id}"

    def _validate_required_fields(self) -> None:
        missing: list[str] = []
        for name in self.REQUIRED_FIELDS:
            if field := self.FIELDS.get(name):
                try:
                    val = self._data[name]
                except KeyError:
                    if (d := field.default) is not None:
                        self._data[name] = d
                        continue
                else:
                    if not val:
                        missing.append(name)
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
