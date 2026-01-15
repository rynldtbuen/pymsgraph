from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Generic, TypeVar, overload, override

from pymsgraph.utils import get_model_class, to_camel_case

if TYPE_CHECKING:
    from pymsgraph.models.base import Model
    from pymsgraph.models.query import QuerySet

__all__ = [
    "BooleanField",
    "CharField",
    "DateTimeField",
    "EmailField",
    "Field",
    "IntegerField",
    "ListField",
    "ModelField",
    "QuerySetField",
]

_T = TypeVar("_T")
_Tm = TypeVar("_Tm", bound="Model")
_Tqs = TypeVar("_Tqs", bound="QuerySet")


class Field(Generic[_T]):
    def __init__(
        self,
        *,
        default: Any = None,
        required: bool = False,
        read_only: bool = False,
        write_only: bool = False,
        select_default: bool = False,
        order_by: bool = False,
        graph_attr_name: str | None = None,
    ) -> None:
        self.name: str
        self.graph_attr_name = graph_attr_name
        self.default = default
        self.required: bool = required
        self.read_only: bool = read_only
        self.write_only: bool = write_only
        self.select_default: bool = select_default
        self.order_by = order_by

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
    def __get__(self, obj: None, owner: type["Model"] | None = None) -> "Field[_T]": ...

    @overload
    def __get__(self, obj: "Model", owner: type["Model"] | None = None) -> _T: ...

    def __get__(
        self, obj: "Model | None", owner: type["Model"] | None = None
    ) -> "_T | Field[_T] | None":
        if obj is None:
            return self
        return obj._data.get(self.name)

    def __set__(self, obj: "Model", value: Any) -> None:
        if (self.read_only or obj.READ_ONLY) and not obj._initializing:
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

    @override
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


class DateTimeField(Field[datetime]):
    @overload
    def __get__(
        self, obj: None, owner: type["Model"] | None = None
    ) -> Field[datetime]: ...

    @overload
    def __get__(
        self, obj: "Model", owner: type["Model"] | None = None
    ) -> datetime: ...

    def __get__(
        self, obj: "Model | None", owner: type["Model"] | None = None
    ) -> Field[datetime] | datetime | None:
        if obj is None:
            return self
        value = obj._data.get(self.name)
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value.astimezone()
        return value

    def __set__(self, obj: "Model", value: Any) -> None:
        if value is not None:
            if isinstance(value, str):
                val = value.strip()
                if val.endswith("Z"):
                    val = f"{val[:-1]}+00:00"
                try:
                    value = datetime.fromisoformat(val)
                except ValueError:
                    raise ValueError(f"{self.name} must be ISO 8601 datetime") from None
            elif not isinstance(value, datetime):
                raise TypeError(
                    f"{self.name} must be datetime (got {type(value).__name__})"
                )
        super().__set__(obj, value)

    def to_graph(self, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError(
                f"{self.name} must be datetime (got {type(value).__name__})"
            )
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        iso = value.isoformat()
        return iso.replace("+00:00", "Z")


class ListField(Field[list[Any]]):
    def __init__(self, item_type: type = str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.item_type = item_type

    def __set__(self, obj: "Model", value: Any) -> None:
        if value is not None:
            if isinstance(value, (str, bytes)):
                raise TypeError(
                    f"{self.name} must be a list (got {type(value).__name__})"
                )
            if not isinstance(value, (list, tuple)):
                raise TypeError(
                    f"{self.name} must be a list (got {type(value).__name__})"
                )
            items = list(value)
            if self.item_type is not None:
                coerced: list[Any] = []
                for item in items:
                    if item is None:
                        coerced.append(item)
                        continue
                    if not isinstance(item, self.item_type):
                        try:
                            item = self.item_type(item)
                        except Exception:
                            raise TypeError(
                                f"{self.name} items must be {self.item_type.__name__}"
                            ) from None
                    coerced.append(item)
                items = coerced
            value = items
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


# class Context:
#     def __init__(self, cache_objects: Any, instance: Model):
#         self.cache_objects = cache_objects
#         self.instance = instance


class QuerySetField(Field["_Tqs"]):
    def __init__(
        self,
        queryset_class: type["_Tqs"],
        *,
        path: str | None = None,
        model_class: "type[Model] | str | None" = None,
        prefetch: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.queryset_class = queryset_class
        self.path = path
        self.prefetch = prefetch
        qs_model_class: type[Model] | None = getattr(
            queryset_class, "model_class", None
        )
        self.model_class = model_class or qs_model_class

    @overload
    def __get__(
        self, obj: None, owner: type["Model"] | None = None
    ) -> "QuerySetField[_Tqs]": ...

    @overload
    def __get__(self, obj: "Model", owner: type["Model"] | None = None) -> "_Tqs": ...

    def __get__(
        self, obj: "Model | None", owner: type["Model"] | None = None
    ) -> "_Tqs | Field[_Tqs]":
        if obj is None:
            return self

        if (model_class := self.model_class) is None:
            raise ValueError(f"{type(self)} model_class is missing.")
        if isinstance(model_class, str):
            model_class = get_model_class(model_class)

        queryset_class = self.queryset_class

        path = self.path or queryset_class.PATH or model_class.PATH
        if path is None:
            if not model_class.HAS_ID:
                path = self.path
            else:
                raise ValueError(f"{type(self)} path is missing.")
        else:
            path = f"{obj.path}/{path.lstrip('/')}"

        kwargs = {"path": path, "model_class": model_class, "obj": obj}
        if cached_data := obj._data.get(self.name):
            kwargs["cached_data"] = cached_data
        if hasattr(obj, "_prefetch_meta"):
            meta = obj._prefetch_meta.get(self.name, {})
            if meta.get("next_link"):
                kwargs["prefetch_next_link"] = meta["next_link"]
            if meta.get("count") is not None:
                kwargs["prefetch_count"] = int(meta["count"])
        return queryset_class(getattr(obj, "_client", None), **kwargs)
