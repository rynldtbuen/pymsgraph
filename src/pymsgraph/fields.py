from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from pymsgraph.models.base import Model


def snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


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
    ) -> None:
        self.name: str = ""  # set by __set_name__
        self.graph_name: str | None = graph_name
        self.default = default
        self.required = required
        self.read_only = read_only
        self.dump = dump
        self.load = load

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
    """A concrete string field."""

    def __init__(
        self,
        graph_name: str | None = None,
        *,
        default: Any = None,
        required: bool = False,
        read_only: bool = False,
        max_length: int | None = None,
        dump: Callable[[Any], Any] | None = None,
        load: Callable[[Any], Any] | None = None,
    ) -> None:
        super().__init__(
            graph_name,
            default=default,
            required=required,
            read_only=read_only,
            dump=dump,
            load=load,
        )
        self.max_length = max_length

    def to_python(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{self.name} must be str (got {type(value).__name__})")
        if self.max_length is not None and len(value) > self.max_length:
            raise ValueError(f"{self.name} exceeds max_length={self.max_length}")
        return " ".join([i.strip() for i in value.split(" ")])


class EmailField(CharField):
    """A concrete email-ish field.

    Intended for Graph properties like `mail` and `userPrincipalName`.

    Design goals:
    - Useful validation (catch obvious mistakes)
    - Not RFC-perfect (Graph/Entra remains source-of-truth)

    By default, requires a single '@' and a '.' in the domain.
    """

    def __init__(
        self,
        graph_name: str | None = None,
        *,
        default: Any = None,
        required: bool = False,
        read_only: bool = False,
        max_length: int | None = None,
        dump: Callable[[Any], Any] | None = None,
        load: Callable[[Any], Any] | None = None,
    ) -> None:
        super().__init__(
            graph_name,
            default=default,
            required=required,
            read_only=read_only,
            max_length=max_length,
            dump=dump,
            load=load,
        )

    def to_python(self, value: Any) -> str | None:
        s = super().to_python(value)
        if s is None:
            return None

        local, _, domain = s.rpartition("@")
        if not local or not domain:
            raise ValueError(f"Invalid email address, '{self.name}'")

        if domain.startswith(".") or domain.endswith(".") or ".." in domain:
            raise ValueError(f"Invalid domain, '{self.name}'")

        if len(local) < 4:
            raise ValueError(
                f"Mail nickname should be least three characters long, '{self.name}'"
            )

        return f"{local}@{domain.lower()}"


class IntegerField(Field):
    """A concrete integer field."""

    def to_python(self, value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise TypeError(f"{self.name} must be int (got bool)")
        if not isinstance(value, int):
            raise TypeError(f"{self.name} must be int (got {type(value).__name__})")
        return value


class DateTimeField(Field):
    """A concrete datetime field."""

    def __init__(
        self,
        graph_name: str | None = None,
        *,
        default: Any = None,
        required: bool = False,
        read_only: bool = False,
        assume_utc: bool = True,
        dump: Callable[[Any], Any] | None = None,
        load: Callable[[Any], Any] | None = None,
    ) -> None:
        super().__init__(
            graph_name,
            default=default,
            required=required,
            read_only=read_only,
            dump=dump,
            load=load,
        )
        self.assume_utc = assume_utc

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

        if dt.tzinfo is None and self.assume_utc:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def to_graph(self, value: Any) -> Any:
        from datetime import datetime, timezone

        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError(
                f"{self.name} must be datetime (got {type(value).__name__})"
            )

        dt = value
        if dt.tzinfo is None and self.assume_utc:
            dt = dt.replace(tzinfo=timezone.utc)

        s = dt.isoformat()
        return s.replace("+00:00", "Z")


class BooleanField(Field):
    """A concrete boolean field."""

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

            from_graph = getattr(self.obj_type, "from_graph", None)
            if callable(from_graph):
                return from_graph(v)

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
