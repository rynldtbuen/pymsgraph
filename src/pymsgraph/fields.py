import datetime
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Field(ABC, Generic[T]):
    def __init__(
        self,
        is_readonly: bool = True,
        fallback: str | None = None,
        to_field: str | None = None,
    ):
        self.is_readonly = is_readonly
        self.fallback = fallback
        self.to_field = to_field

    def __set_name__(self, owner, name):
        self._name = name
        names = name.split("_")
        self.name = "".join([names[0]] + [i.title() for i in names[1:]])

    def __get__(self, obj, objtype=None) -> T | None:
        # if obj is None:
        #     return self
        name = self.name
        if self.to_field:
            name = self.to_field
        try:
            val = obj._data[name]
        except KeyError:
            if self.fallback:
                return self.get_value(getattr(obj, f"_{self.fallback}", None))
            return None
        else:
            return self.get_value(val)

    def __set__(self, obj, value) -> None:
        if self.is_readonly:
            raise AttributeError(f"Attribute '{self.name}' is read-only.")

    def __delete__(self, obj) -> None:
        if self.is_readonly:
            raise AttributeError(f"Attribute '{self.name}' is read-only.")

    @abstractmethod
    def get_value(self, *args, **kwargs) -> T:
        pass


class DictField(Field[dict]):
    def get_value(self, val: dict) -> dict:
        return val


class CharField(Field[str]):
    def get_value(self, val: Any) -> str:
        return str(val)


class IntegerField(Field[int]):
    def get_value(self, val: str | int) -> int:
        return int(val)


class DateTimeField(Field[datetime.datetime]):
    def get_value(self, val: Any) -> datetime.datetime:
        return datetime.datetime.fromisoformat(str(val))


class BooleanField(Field[bool]):
    def get_value(self, val: Any) -> bool:
        return bool(val)
