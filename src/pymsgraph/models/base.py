from __future__ import annotations

__all__ = ["Model"]

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Self

from pymsgraph.models.fields import CharField, Field
from pymsgraph.utils import to_snake_case

if TYPE_CHECKING:
    from pymsgraph.client import Client


class Model:
    REQUIRED_FIELDS: frozenset[str]
    FIELD_NAME_MAP: dict[str, str]
    WRITE_ON_FIELDS: frozenset[str]
    DEFAULT_SELECT_FIELDS: tuple[str, ...] | None = None
    SEARCH_FIELD: str | None = None
    HAS_ID: bool = True
    READ_ONLY: bool = False
    PATH: str | None = None

    id = CharField(read_only=True, select_default=True)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        fields: dict[str, Field] = {}
        required_fields: set[str] = set()
        field_name_map: dict[str, str] = {}
        write_fields: set[str] = set()
        default_select: set[str] = set()

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
                        default_select.add(name)

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
                    default_select.add(name)

        cls.FIELDS = fields
        cls.REQUIRED_FIELDS = frozenset(required_fields)
        cls.FIELD_NAME_MAP = field_name_map
        cls.WRITE_FIELDS = frozenset(write_fields)
        if len(default_select) > 1:
            cls.DEFAULT_SELECT_FIELDS = tuple(sorted(default_select))

    def __init__(
        self,
        *,
        client: "Client | None" = None,
        path: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._data: dict[str, Any] = {}
        self._graph_data: dict[str, Any] = {}
        self._dirty: set[str] = set()
        self._prefetch_meta: dict[str, dict[str, Any]] = {}
        self._args: tuple[Any, ...] = (client, path or self.PATH)

        self._initializing = True
        for k, v in kwargs.items():
            setattr(self, k, v)
        self._initializing = False

    @property
    def path(self) -> str:
        if not self.HAS_ID:
            if (p := self.PATH) and (e := self._args[1]):
                return f"{e}{p}"
            raise ValueError(f"{type(self).__name__} does not have a resource path")
        if self.id is None:
            raise AttributeError(f"{type(self).__name__} object has no attribute, 'id'")
        if e := self._args[1]:
            return f"{e}/{self.id}"
        raise AttributeError(f"{type(self).__name__} object has no attribute 'path'")

    def to_dict(self) -> dict[str, Any]:
        def _coerce(val: Any) -> Any:
            if isinstance(val, Model):
                return val.to_dict()
            if isinstance(val, list):
                return [_coerce(v) for v in val]
            if isinstance(val, dict):
                return {k: _coerce(v) for k, v in val.items()}
            return val

        return {k: _coerce(getattr(self, k, None)) for k in self.FIELDS}

    def serialize(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        attr_names = set(self._dirty or self._data.keys())

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

    async def update(self, data: dict[str, Any] | None = None) -> bool:
        if self.READ_ONLY:
            raise ValueError(f"{type(self).__name__} does not support update")

        path = self.path
        if data is not None:
            for k, v in data.items():
                try:
                    self.FIELDS[k]
                except KeyError:
                    continue
                setattr(self, k, v)

        if not (body := self.serialize()):
            return False

        await self._client.patch(path, body=body)
        self._dirty.clear()
        return True

    async def delete(self, force: bool = False) -> None:
        if self.READ_ONLY:
            raise ValueError(f"{type(self).__name__} object does not support delete")

        if not force:
            raise RuntimeError("Call delete(force=True) to proceed.")

        await self._client.delete(self.path)

        self._data.clear()
        self._dirty.clear()

    def refresh_from_graph(self, data: dict[str, Any]) -> None:
        self._data = self.__class__.from_graph(data)._data

    @classmethod
    def from_graph(
        cls,
        data: dict[str, Any],
        *,
        client: "Client | None" = None,
        path: str | None = None,
    ) -> Self:
        data = deepcopy(data)
        obj = cls(client=client, path=path or cls.PATH)

        obj._initializing = True
        for graph_attr_name, val in data.items():
            py_attr_name = cls.FIELD_NAME_MAP.get(
                graph_attr_name, to_snake_case(graph_attr_name)
            )
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
                        if val is None:
                            missing.append(name)
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")


class PropertyModel(Model):
    HAS_ID = False


class ReadOnlyModel(Model):
    READ_ONLY = True
