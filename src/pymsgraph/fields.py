from __future__ import annotations

from collections.abc import Callable
from typing import Any, TYPE_CHECKING, Generic, Protocol, Self, TypeVar

if TYPE_CHECKING:
    from pymsgraph.models.base import GraphModel


class FieldSerializable(Protocol):
    @classmethod
    def from_graph(cls, payload: dict[str, Any]) -> Self: ...
    def to_graph(self) -> dict[str, Any]: ...


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

    def __set_name__(self, owner: type[GraphModel], name: str) -> None:
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

    def _get_raw(self, instance: GraphModel) -> Any:
        return instance._data.get(self.name, self.default)

    def __get__(self, instance: GraphModel | None, owner: type[GraphModel]) -> Any:
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

    def __set__(self, instance: GraphModel, value: Any) -> None:
        # Normalize to python representation on assignment.
        py_val = self.to_python(value)
        instance._data[self.name] = py_val

        if not instance._initializing and not self.read_only:
            instance._dirty.add(self.name)


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
        strip: bool = False,
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
        self.strip = strip

    def to_python(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{self.name} must be str (got {type(value).__name__})")
        if self.strip:
            value = value.strip()
        if self.max_length is not None and len(value) > self.max_length:
            raise ValueError(f"{self.name} exceeds max_length={self.max_length}")
        return value


class EmailField(CharField):
    """A concrete email-ish field.

    Intended for Graph properties like `mail` and `userPrincipalName`.

    Design goals:
    - Useful validation (catch obvious mistakes)
    - Not RFC-perfect (Graph/Entra remains source-of-truth)

    By default requires a single '@' and a '.' in the domain.
    """

    def __init__(
        self,
        graph_name: str | None = None,
        *,
        default: Any = None,
        required: bool = False,
        read_only: bool = False,
        max_length: int | None = None,
        strip: bool = True,
        allow_blank: bool = False,
        allow_domain_without_dot: bool = False,
        normalize_domain: bool = True,
        dump: Callable[[Any], Any] | None = None,
        load: Callable[[Any], Any] | None = None,
    ) -> None:
        super().__init__(
            graph_name,
            default=default,
            required=required,
            read_only=read_only,
            max_length=max_length,
            strip=strip,
            dump=dump,
            load=load,
        )
        self.allow_blank = allow_blank
        self.allow_domain_without_dot = allow_domain_without_dot
        self.normalize_domain = normalize_domain

    def to_python(self, value: Any) -> str | None:
        s = super().to_python(value)
        if s is None:
            return None

        if s == "":
            if self.allow_blank:
                return s
            raise ValueError(f"{self.name} must not be blank")

        if any(ch.isspace() for ch in s):
            raise ValueError(f"{self.name} must not contain whitespace")
        if s.count("@") != 1:
            raise ValueError(f"{self.name} must contain a single '@'")

        local, _, domain = s.rpartition("@")
        if not local or not domain:
            raise ValueError(f"{self.name} must look like local@domain")

        if not self.allow_domain_without_dot and "." not in domain:
            raise ValueError(f"{self.name} domain must contain a '.'")

        if domain.startswith(".") or domain.endswith(".") or ".." in domain:
            raise ValueError(f"{self.name} domain is invalid")

        if self.normalize_domain:
            s = f"{local}@{domain.lower()}"

        return s


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


TObj = TypeVar("TObj", bound=FieldSerializable)


class ObjectField(Field, Generic[TObj]):
    def __init__(
        self, obj_type: type[TObj], graph_name: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(graph_name, **kwargs)
        self.obj_type = obj_type

    def to_python(self, value: Any) -> TObj | None:
        if value is None:
            return None
        if isinstance(value, self.obj_type):
            return value
        if isinstance(value, dict):
            return self.obj_type.from_graph(value)
        raise TypeError(f"{self.name} must be {self.obj_type.__name__} or dict")

    def to_graph(self, value: Any) -> Any:
        if value is None:
            return None
        obj = self.to_python(value)
        return obj.to_graph() if obj is not None else None
