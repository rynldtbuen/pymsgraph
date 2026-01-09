from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast, overload

from pymsgraph.utils import get_model_class, to_camel_case

if TYPE_CHECKING:
    from pymsgraph.models.base import Model
    from pymsgraph.models.query import QuerySet

__all__ = [
    "BooleanField",
    "CharField",
    "EmailField",
    "Field",
    "IntegerField",
    "ModelField",
    "QuerySetField",
]

_Tf = TypeVar("_Tf")
_Tm = TypeVar("_Tm", bound="Model")


class Field(Generic[_Tf]):
    def __init__(
        self,
        *,
        default: Any = None,
        required: bool = False,
        read_only: bool = False,
        write_only: bool = False,
        select_default: bool = False,
        graph_attr_name: str | None = None,
    ) -> None:
        self.name: str
        self.graph_attr_name = graph_attr_name
        self.default = default
        self.required = required
        self.read_only = read_only
        self.write_only = write_only
        self.select_default = select_default

        if read_only and write_only:
            raise ValueError(
                f"Field can't be both read_only and write_only, '{type(self)}'."
            )

    def __set_name__(self, owner: type["Model"], name: str) -> None:
        self.name = name
        if self.graph_attr_name is None:
            self.graph_attr_name = to_camel_case(name)

    def to_graph(self, value: Any) -> Any:
        return value

    @overload
    def __get__(
        self, obj: None, owner: type["Model"] | None = None
    ) -> "Field[_Tf]": ...

    @overload
    def __get__(self, obj: "Model", owner: type["Model"] | None = None) -> _Tf: ...

    def __get__(
        self, obj: "Model | None", owner: type["Model"] | None = None
    ) -> _Tf | "Field[_Tf]" | None:
        if obj is None:
            return self
        return obj._data.get(self.name)

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
        *,
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
    def __set__(self, obj: "Model", value: str) -> None:
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


class ModelField(Field[_Tm]):
    def __init__(
        self,
        model_class: type[_Tm],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.model_class = model_class

    def __set__(self, obj: "Model", value: Any) -> None:
        if value is None:
            super().__set__(obj, None)
            return
        if isinstance(value, dict):
            value = self.model_class(**value)
        if not isinstance(value, self.model_class):
            raise TypeError(
                f"{self.name} must be {self.model_class.__name__} (got {type(value).__name__})"
            )
        super().__set__(obj, value)

    def to_graph(self, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, self.model_class):
            raise TypeError(
                f"{self.name} must be {self.model_class.__name__} (got {type(value).__name__})"
            )
        return value.serialize()


class QuerySetField(Field["QuerySet[_Tm]"]):
    def __init__(
        self,
        queryset_class: type["QuerySet[_Tm]"],
        *,
        endpoint: str | None = None,
        model_class: type[_Tm] | str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.queryset_class = queryset_class
        self.endpoint = endpoint or getattr(model_class, "endpoint", None)
        self.model_class = model_class or getattr(queryset_class, "model_class", None)
        self._cache: dict[int, Any] = {}

    @overload
    def __get__(
        self, obj: None, owner: type["Model"] | None = None
    ) -> "QuerySetField[_Tm]": ...

    @overload
    def __get__(
        self, obj: "Model[_Tm]", owner: type["Model"] | None = None
    ) -> "QuerySet[_Tm]": ...

    def __get__(
        self, obj: "Model[_Tm] | None", owner: type["Model"] | None = None
    ) -> "QuerySet[_Tm] | Field[QuerySet[_Tm]]":
        if obj is None:
            return self

        if (model_class := self.model_class) is None:
            raise ValueError(f"{type(self)} model_class is missing.")
        if isinstance(model_class, str):
            model_class = get_model_class(model_class)
        model_class = cast(type[_Tm], model_class)

        if (endpoint := self.endpoint) is None:
            raise ValueError(f"{type(self)} endpoint is missing.")
        endpoint = f"{obj._endpoint}/{endpoint.lstrip('/')}"

        kwargs = {"endpoint": endpoint, "model_class": model_class}
        if cached_data := obj._data.get(self.name):
            kwargs["cached_data"] = cached_data
        return self.queryset_class(obj._client, **kwargs)
