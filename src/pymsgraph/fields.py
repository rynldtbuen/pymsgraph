from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pymsgraph.utils import snake_to_camel

if TYPE_CHECKING:
    from pymsgraph.models.base import Model, TModel
    from pymsgraph.query import QuerySet


class Field:
    def __init__(
        self,
        graph_name: str | None = None,
        *,
        default: Any = None,
        required: bool = False,
        read_only: bool = False,
        dump: Callable[[Any], Any] | None = None,  # python -> json
        load: Callable[[Any], Any] | None = None,  # json -> python
        supported_lookups: set[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.name: str = ""  # set by __set_name__
        self.graph_name: str | None = graph_name
        self.default = default
        self.required = required
        self.read_only = read_only
        self.dump = dump
        self.load = load
        self.supported_lookups = set(supported_lookups or set())

        for k, v in kwargs.items():
            setattr(self, k, v)

    def __set_name__(self, owner: type[Model], name: str) -> None:
        self.name = name
        if self.graph_name is None:
            self.graph_name = snake_to_camel(name)

    # --- conversion hooks ---
    def to_python(self, value: Any) -> Any:
        """Graph JSON -> python value."""
        return self.load(value) if self.load else value

    def to_graph(self, value: Any) -> Any:
        """Python value -> Graph JSON."""
        return self.dump(value) if self.dump else value

    def _get_raw(self, instance: Model) -> Any:
        return instance._data.get(self.name, self.default)

    def __get__(self, instance: Model | None, owner: type[Model]) -> Any:
        if instance is None:
            return self

        raw = self._get_raw(instance)
        if raw is None:
            return None

        py_val = self.to_python(raw)

        # Optional caching: if raw != python form, replace without marking dirty.
        if py_val is not raw:
            instance._data[self.name] = py_val

        return py_val

    def __set__(self, obj: Model, value: Any) -> None:
        py_val = self.to_python(value)
        prev = obj._data.get(self.name, self.default)
        obj._data[self.name] = py_val

        if getattr(obj, "_initializing", False):
            return
        if self.read_only:
            raise AttributeError(f"{self.name} is read-only")
        if prev != py_val:
            obj._dirty.add(self.name)


class CharField(Field):

    def to_python(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{self.name} must be str (got {type(value).__name__})")
        ml = int(getattr(self, "max_length", 0))
        if ml and len(value) > ml:
            raise ValueError(f"{self.name} exceeds max_length={ml}")
        return " ".join([i.strip() for i in value.strip().split(" ")])


class EmailField(CharField):

    def to_python(self, value: Any) -> str | None:
        s = super().to_python(value)
        if s is None:
            return None

        local, _, domain = s.rpartition("@")
        if not local or not domain:
            raise ValueError(f"Invalid email address, '{self.name}'")

        if domain.startswith(".") or domain.endswith(".") or ".." in domain:
            raise ValueError(f"Invalid domain, '{self.name}'")

        if len(local) < 2:
            raise ValueError(
                f"Mail nickname should be least two characters long, '{self.name}'"
            )

        return f"{local}@{domain.lower()}"


class IntegerField(Field):

    def to_python(self, value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise TypeError(f"{self.name} must be int (got bool)")
        if not isinstance(value, int):
            raise TypeError(f"{self.name} must be int (got {type(value).__name__})")
        return value


class DateTimeField(Field):

    def to_python(self, value: Any):
        from datetime import datetime, timezone

        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            s = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
        else:
            raise TypeError(
                f"{self.name} must be datetime or ISO 8601 str (got {type(value).__name__})"
            )

        return dt.replace(tzinfo=timezone.utc)

    def to_graph(self, value: Any) -> Any:
        from datetime import datetime, timezone

        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError(
                f"{self.name} must be datetime (got {type(value).__name__})"
            )

        dt = value.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")


class BooleanField(Field):

    def to_python(self, value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        raise TypeError(f"{self.name} must be bool (got {type(value).__name__})")


T = TypeVar("T")


class ObjectField(Field, Generic[T]):
    """
    Field that auto-hydrates nested Graph objects into a Python type.

    Supports:
      - dict  -> T.from_graph(dict)  (or T(**dict) fallback)
      - list[dict] -> list[T]   (auto-detected unless many=False)
      - T instances pass through

    Examples:
        prepaid_units = ObjectField(LicenseUnitsDetail)
        service_plans = ObjectField(ServicePlanInfo)  # list will auto-hydrate
        service_plans = ObjectField(ServicePlanInfo, many=True)  # explicit
    """

    def __init__(
        self,
        obj_type: type[T],
        *,
        many: bool | None = None,
        factory: Callable[[dict[str, Any]], T] | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.obj_type = obj_type
        self.many = many
        self.factory = factory

    # ---- Model hooks (these names cover most Field implementations) ----
    # If your base Field uses different hook names, just alias these to whatever
    # Model calls (e.g. to_python / from_graph_value / clean / etc.)

    def to_python(self, value: Any) -> Any:
        if value is None:
            return None

        if self.many is True or (self.many is None and isinstance(value, list)):
            return [self._one_to_python(v) for v in (value or [])]

        return self._one_to_python(value)

    def to_graph(self, value: Any) -> Any:
        if value is None:
            return None

        if self.many is True or (self.many is None and isinstance(value, list)):
            return [self._one_to_graph(v) for v in (value or [])]

        return self._one_to_graph(value)

    # ---- internal helpers ----

    def _one_to_python(self, v: Any) -> Any:
        if v is None:
            return None

        # Already hydrated
        if isinstance(v, self.obj_type):
            return v

        # Graph gives dicts for complex types
        if isinstance(v, dict):
            if self.factory is not None:
                return self.factory(v)

            # from_graph = getattr(self.obj_type, "from_graph", None)
            # if callable(from_graph):
            #     return from_graph(v)

            # fallback: dataclass / normal ctor
            return self.obj_type(**v)  # type: ignore[misc]

        # Unknown shape: pass through
        return v

    def _one_to_graph(self, v: Any) -> Any:
        if v is None:
            return None

        if isinstance(v, dict):
            return v

        # dataclass instance
        if is_dataclass(v):
            return asdict(v)  # type: ignore

        # model-like / dt-like with to_graph()
        to_graph = getattr(v, "to_graph", None)
        if callable(to_graph):
            return to_graph()

        # last resort: pass through
        return v


class QuerySetField(Field):
    def __init__(
        self,
        queryset_class: type[QuerySet[TModel]],
        graph_name: str | None = None,
        *,
        is_related: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(graph_name=graph_name, is_related=is_related, **kwargs)
        self.queryset_class = queryset_class

    def __get__(self, obj: Any, objtype=None):
        if obj is None:
            return self
        try:
            return getattr(obj, f"_{self.name}_qs")
        except AttributeError:
            qs = self.queryset_class(parent=obj)

            raw = obj._data.get(self.name) if hasattr(obj, "_data") else None
            if raw is None and hasattr(obj, "_graph_data"):
                raw = obj._graph_data.get(self.graph_name or self.name)

            if raw is not None:
                if isinstance(raw, list):
                    qs._objects = [  # pyright: ignore[reportAttributeAccessIssue]
                        qs.make_from_graph(data) for data in raw
                    ]
                elif isinstance(raw, dict):
                    qs._objects = [  # pyright: ignore[reportAttributeAccessIssue]
                        qs.make_from_graph(raw)
                    ]
                else:
                    raise RuntimeError(f"Unsupported Graph data, {type(raw)}, {raw}")
                qs._changed = False

            setattr(obj, f"_{self.name}_qs", qs)
            return qs
