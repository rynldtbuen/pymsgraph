from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pymsgraph.utils import to_camel_case

if TYPE_CHECKING:
    from pymsgraph.models.base import Model

T = TypeVar("T")


class Field(Generic[T]):
    def __init__(
        self,
        *,
        default: Any = None,
        required: bool = False,
        read_only: bool = False,
        graph_attr_name: str | None = None,
    ) -> None:
        self.name: str = ""
        self.graph_attr_name = graph_attr_name
        self.default = default
        self.required = required
        self.read_only = read_only

    def __set_name__(self, owner: type["Model"], name: str) -> None:
        self.name = name
        if self.graph_attr_name is None:
            self.graph_attr_name = to_camel_case(name)

    def to_graph(self, value: Any) -> Any:
        return value

    def __get__(
        self, obj: "Model | None", owner: type["Model"] | None = None
    ) -> T | "Field[T]":
        if obj is None:
            return self
        return obj._data.get(self.name, self.default)

    def __set__(self, obj: "Model", value: Any) -> None:
        if self.read_only and not obj._initializing:
            raise AttributeError(f"{self.name} is read-only")

        prev_val = self.__get__(obj)
        obj._data[self.name] = value

        if obj._initializing:
            return

        if prev_val != value:
            obj._dirty.add(self.name)

    def __delete__(self, obj: "Model") -> None:
        self.__set__(obj, value=None)


class CharField(Field[str]):
    def __init__(
        self,
        min_length: int | None = None,
        max_length: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.min_length = min_length
        self.max_length = max_length

    def _check_length(self, value: str) -> None:
        if self.min_length is not None and len(value) < self.min_length:
            raise ValueError(f"{self.name} must be at least {self.min_length} chars")
        if self.max_length is not None and len(value) > self.max_length:
            raise ValueError(f"{self.name} exceeds max_length={self.max_length}")

    def __set__(self, obj: "Model", value: Any) -> None:
        if value is not None:
            if not isinstance(value, str):
                raise TypeError(f"{self.name} must be str (got {type(value).__name__})")

            value = " ".join(value.split())
            self._check_length(value)

        super().__set__(obj, value)


class IntegerField(Field[int]):
    def __set__(self, obj: "Model", value: Any) -> None:
        if value is not None:
            if isinstance(value, bool):
                raise TypeError(f"{self.name} must be int (got bool)")
            if not isinstance(value, int):
                try:
                    value = int(value)
                except Exception:
                    raise TypeError(
                        f"{self.name} must be int (got {type(value).__name__})"
                    ) from None
        super().__set__(obj, value)


class BooleanField(Field[bool]):
    def __set__(self, obj: "Model", value: Any) -> None:
        if value is not None and not isinstance(value, bool):
            if isinstance(value, int):
                value = bool(value)
            elif isinstance(value, str):
                s = value.strip().lower()
                if s in {"true", "false"}:
                    value = s == "true"
                else:
                    try:
                        value = bool(int(s))
                    except Exception:
                        raise TypeError(
                            f"{self.name} must be bool (got {type(value).__name__})"
                        ) from None
            else:
                raise TypeError(
                    f"{self.name} must be bool (got {type(value).__name__})"
                )
        super().__set__(obj, value)


class EmailField(CharField):
    def __set__(self, obj: "Model", value: Any) -> None:
        if value is not None:
            if not isinstance(value, str):
                raise TypeError(f"{self.name} must be str (got {type(value).__name__})")

            value = "".join(value.split())
            self._check_length(value)
            local, sep, domain = value.rpartition("@")
            if not local or not sep or not domain:
                raise ValueError(f"Invalid email address for {self.name}")
            if domain.startswith(".") or domain.endswith(".") or ".." in domain:
                raise ValueError(f"Invalid domain for {self.name}")

        super().__set__(obj, value)
