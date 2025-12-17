from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, Generic, TYPE_CHECKING, TypeVar

from pymsgraph.queryset import QuerySet

if TYPE_CHECKING:
    from pymsgraph.models.base import GraphModel


TModel = TypeVar("TModel", bound="GraphModel")


type QuerySetClass = type["QuerySet[Any]"]


class BaseManager(Generic[TModel]):
    """Django-ish manager with QuerySet method injection.

    `from_queryset()` dynamically creates a Manager subclass and copies public
    QuerySet instance methods onto it as thin wrappers:
        manager.method(*a, **kw) -> self.get_queryset().method(*a, **kw)
    """

    _queryset_class: QuerySetClass

    def __init__(self, model: type[TModel] | None = None, **qs_kwargs: Any) -> None:
        self.model = model
        self._qs_kwargs = qs_kwargs

    @classmethod
    def _get_queryset_methods(
        cls, queryset_class: QuerySetClass
    ) -> dict[str, Callable[..., Any]]:
        def create_method(name: str, method: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(method)
            def manager_method(self, *args: Any, **kwargs: Any) -> Any:
                return getattr(self.get_queryset(), name)(*args, **kwargs)

            return manager_method

        new_methods: dict[str, Callable[..., Any]] = {}

        for name, method in inspect.getmembers(
            queryset_class, predicate=inspect.isfunction
        ):
            # don't override existing manager attrs
            if hasattr(cls, name):
                continue

            queryset_only = getattr(method, "queryset_only", None)

            # skip private methods unless queryset_only explicitly False
            if queryset_only or (queryset_only is None and name.startswith("_")):
                continue

            new_methods[name] = create_method(name, method)

        return new_methods

    @classmethod
    def from_queryset(
        cls,
        queryset_class: QuerySetClass,
        class_name: str | None = None,
    ) -> type["BaseManager[Any]"]:
        class_name = class_name or f"{cls.__name__}From{queryset_class.__name__}"
        return type(
            class_name,
            (cls,),
            {
                "_queryset_class": queryset_class,
                **cls._get_queryset_methods(queryset_class),
            },
        )

    def contribute_to_model(self, model):
        self.model = model
        setattr(model, "objects", ManagerDescriptor(self))

    def get_queryset(self) -> "QuerySet[TModel]":
        return self._queryset_class(self.model, **self._qs_kwargs)  # type: ignore[arg-type]

    def all(self) -> "QuerySet[TModel]":
        return self.get_queryset()


class GraphManager(BaseManager.from_queryset(QuerySet)):
    pass


class ManagerDescriptor:
    def __init__(self, manager=None, model=None):
        self.manager = manager

    def __get__(self, instance, cls=None):
        if instance is not None:
            raise AttributeError(
                "Manager isn't accessible via %s instances" % cls.__name__  # type: ignore
            )

        return self.manager
