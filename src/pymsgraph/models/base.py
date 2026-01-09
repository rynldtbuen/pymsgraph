from __future__ import annotations

__all__ = ["Model"]

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar

from pymsgraph.models.fields import CharField, Field
from pymsgraph.utils import to_snake_case

if TYPE_CHECKING:
    from pymsgraph.client import Client
    from pymsgraph.models.query import QuerySet


_Tm = TypeVar("_Tm", bound="Model")


class Model(Generic[_Tm]):
    REQUIRED_FIELDS: frozenset[str]
    FIELD_NAME_MAP: dict[str, str]
    WRITE_ON_FIELDS: frozenset[str]
    DEFAULT_SELECT_FIELDS: tuple[str, ...]

    read_only: bool = False
    endpoint: str
    standalone: bool = False

    id = CharField(select_default=True)

    def __init_subclass__(cls: type[_Tm], **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        fields: dict[str, Field] = {}
        required_fields: set[str] = set()
        field_name_map: dict[str, str] = {}
        write_fields: set[str] = set()
        default_select: list[str] = []

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
                    if attr.select_default:
                        default_select.append(name)

        for name, attr in cls.__dict__.items():
            if isinstance(attr, Field):
                fields[name] = attr
                if graph_attr_name := attr.graph_attr_name:
                    field_name_map[graph_attr_name] = name
                if attr.required:
                    required_fields.add(name)
                if attr.write_only:
                    write_fields.add(name)
                if attr.select_default:
                    default_select.append(name)

        cls.FIELDS = fields
        cls.REQUIRED_FIELDS = frozenset(required_fields)
        cls.FIELD_NAME_MAP = field_name_map
        cls.WRITE_FIELDS = frozenset(write_fields)
        cls.DEFAULT_SELECT_FIELDS = tuple(default_select)

    def __init__(
        self,
        *,
        client: "Client | None" = None,
        endpoint: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._data: dict[str, Any] = {}
        self._graph_data: dict[str, Any] = {}
        self._dirty: set[str] = set()
        self._args: tuple[Any, ...] = (client, endpoint)

        self._initializing = True
        for k, v in kwargs.items():
            setattr(self, k, v)
        self._initializing = False

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k, None) for k in self.FIELDS}

    def serialize(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        attr_names = set(self._dirty or self._data.keys())
        if self.id is None:
            for name, field in self.FIELDS.items():
                if name not in self._data and field.default is not None:
                    attr_names.add(name)

        for attr_name in attr_names:
            field = self.FIELDS[attr_name]
            if field.read_only:
                continue
            if attr_name in self._data:
                val = self._data[attr_name]
            else:
                val = field.default
            if gr_attr_name := field.graph_attr_name:
                data[gr_attr_name] = field.to_graph(val)

        return data

    async def save(self) -> bool:
        is_create = self.id is None
        if is_create:
            self._validate_for_create()
            client_method = self._client.post
            endpoint = self._args[1]
        else:
            client_method = self._client.patch
            endpoint = self._endpoint

        body = self.serialize()

        if not body:
            return False

        data = await client_method(endpoint, body=body)
        self._dirty.clear()
        if data:
            if is_create:
                merged = dict(data)
                for attr_name, val in self._data.items():
                    field = self.FIELDS.get(attr_name)
                    if field is None or field.write_only:
                        continue
                    graph_attr_name = field.graph_attr_name or attr_name
                    merged.setdefault(graph_attr_name, field.to_graph(val))
                data = merged
            self.refresh_from_graph(data)
        return True

    def refresh_from_graph(self, data: dict[str, Any]) -> None:
        self._data = self.__class__.from_graph(data)._data

    @classmethod
    def from_graph(
        cls,
        data: dict[str, Any],
        client: "Client | None" = None,
        endpoint: str | None = None,
    ) -> Self:
        data = deepcopy(data)
        obj = cls(
            client=client,
            endpoint=endpoint or cls.endpoint,
        )

        obj._initializing = True

        for graph_attr_name, val in data.items():
            py_attr_name = to_snake_case(graph_attr_name)
            if cls.FIELDS.get(py_attr_name):
                setattr(obj, py_attr_name, val)

        obj._graph_data = data
        obj._initializing = False
        return obj

    @property
    def _client(self) -> "Client":
        if c := self._args[0]:
            return c
        raise AttributeError(f"{type(self).__name__} object has no attribute '_client'")

    @property
    def _endpoint(self) -> str:
        if self.id is None:
            raise AttributeError(f"{type(self).__name__} object has no attribute 'id'")
        if e := self._args[1]:
            return f"{e}/{self.id}"
        raise AttributeError(
            f"{type(self).__name__} object has no attribute '_endpoint'"
        )

    def _validate_for_create(self) -> None:
        missing: list[str] = []
        for names in (self.REQUIRED_FIELDS, self.WRITE_FIELDS):
            for name in names:
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
