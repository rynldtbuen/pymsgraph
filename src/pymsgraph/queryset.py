from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable, Iterator
from typing import Any, Generic, TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from pymsgraph.models.base import GraphModel


Lookup = tuple[str, Any, str]  # (field_name, value, lookup)

_LOOKUP_TO_OP: dict[str, str] = {
    "exact": "eq",
    "ne": "ne",
    "gt": "gt",
    "gte": "ge",
    "lt": "lt",
    "lte": "le",
}


def odata_literal(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise TypeError(f"Unsupported literal type: {type(value)!r}")


def compile_lookup(graph_field: str, lookup: str, value: Any) -> str:
    lookup = lookup or "exact"

    if lookup in _LOOKUP_TO_OP:
        return f"{graph_field} {_LOOKUP_TO_OP[lookup]} {odata_literal(value)}"

    if lookup == "contains":
        return f"contains({graph_field}, {odata_literal(value)})"
    if lookup == "startswith":
        return f"startswith({graph_field}, {odata_literal(value)})"
    if lookup == "endswith":
        return f"endswith({graph_field}, {odata_literal(value)})"

    if lookup == "isnull":
        return f"{graph_field} eq null" if value else f"{graph_field} ne null"

    if lookup == "in":
        if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
            raise TypeError("__in expects a non-string iterable")
        parts = [f"{graph_field} eq {odata_literal(v)}" for v in value]
        return "(" + " or ".join(parts) + ")" if parts else "(false)"

    raise ValueError(f"Unsupported lookup: {lookup!r}")


@dataclass(frozen=True)
class Q:
    op: str
    children: tuple["Node", ...]

    def __init__(self, *children: "Node", op: str = "AND", **lookups: Any) -> None:
        kids: list["Node"] = list(children)

        for key, value in lookups.items():
            field, lookup = (key.split("__", 1) + ["exact"])[:2]
            kids.append((field, value, lookup))

        # frozen dataclass -> must use object.__setattr__
        object.__setattr__(self, "op", op.upper())
        object.__setattr__(self, "children", tuple(kids))

    def __and__(self, other: Q) -> Q:
        return Q(self, other, op="AND")

    def __or__(self, other: Q) -> Q:
        return Q(self, other, op="OR")


# Python 3.12 type-alias syntax (PEP 695)
type Node = Q | Lookup


TModel = TypeVar("TModel", bound="GraphModel")


class BaseQuerySet(Generic[TModel]):
    def __init__(
        self,
        model: type[TModel],
        *,
        q: Q | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self._q = q
        self._params = params or {}
        self._headers = headers or {}

        self._kwargs: dict[str, Any] = dict(kwargs)
        self._changed: bool = True
        self._data: dict[str, Any] = {}

    @property
    def endpoint(self):
        return self.model.endpoint

    def __iter__(self) -> Iterator[TModel]:
        if self._changed:
            client = self.model._get_client()
            data = client.get(
                self.endpoint, params=self._build_params(), headers=self._headers
            )
            self._data = data
            self._changed = False
        else:
            data = self._data
        for item in data.get("value", []):
            yield self.model.from_graph(item)

    def only(self, *fields: str) -> BaseQuerySet[TModel]:
        graph_fields = [self.model._meta.field_to_graph(f) for f in fields]
        p = dict(self._params)
        p["$select"] = ",".join(graph_fields)
        return self._clone(params=p)

    def _clone(
        self,
        *,
        q: Q | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> BaseQuerySet[TModel]:

        return self.__class__(
            self.model,
            q=q or self._q,
            params=dict(self._params) if params is None else params,
            headers=dict(self._headers) if headers is None else headers,
            **dict(self._kwargs),
        )

    def _compile_q(self, q: Q) -> str:
        def compile_node(node: Node) -> str:
            if isinstance(node, Q):
                inner = f" {node.op.lower()} ".join(
                    compile_node(c) for c in node.children
                )
                return f"({inner})"

            field_name, value, lookup = node
            gf = self.model._meta.field_to_graph(field_name)
            return compile_lookup(gf, lookup, value)

        return compile_node(q)

    def _build_params(self) -> dict[str, Any]:
        p = dict(self._params)
        parts: list[str] = []
        if self._q is not None:
            parts.append(self._compile_q(self._q))
        if parts:
            p["$filter"] = " and ".join(parts)
        return p


class QuerySet(Generic[TModel]):
    def __init__(
        self,
        model: type[TModel],
        *,
        q: Q | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self._q = q
        self._params = params or {}
        self._headers = headers or {}

        self._kwargs: dict[str, Any] = dict(kwargs)
        self._changed: bool = True
        self._data: dict[str, Any] = {}

    @classmethod
    def as_manager(cls):
        from .manager import BaseManager

        return BaseManager.from_queryset(cls)()

    @property
    def endpoint(self):
        return self.model.endpoint

    def __iter__(self) -> Iterator[TModel]:
        if self._changed:
            client = self.model._get_client()
            data = client.get(
                self.endpoint, params=self._build_params(), headers=self._headers
            )
            self._data = data
            self._changed = False
        else:
            data = self._data
        for item in data.get("value", []):
            yield self.model.from_graph(item)

    def __getitem__(self, key: slice | int) -> "QuerySet[TModel]":
        if isinstance(key, int):
            # Optional: Django-style would execute and return an item.
            # For a purely-lazy QuerySet, returning a sliced QuerySet is simplest:
            if key < 0:
                raise IndexError(
                    "Negative indexes are not supported for Graph querysets."
                )
            return self[key : key + 1]

        if key.step not in (None, 1):
            raise TypeError("Slicing with a step is not supported (use [:N] or [A:B]).")

        start = 0 if key.start is None else key.start
        stop = key.stop

        if start < 0 or (stop is not None and stop < 0):
            raise IndexError("Negative slicing is not supported for Graph querysets.")

        p = dict(self._params or {})

        # read existing paging state (if any)
        base_skip = int(p.get("$skip", 0) or 0)
        base_top = int(p["$top"]) if "$top" in p and p["$top"] is not None else None

        # new skip is relative to existing skip
        new_skip = base_skip + start

        # compute new top (limit)
        if stop is None:
            new_top = None if base_top is None else max(base_top - start, 0)
        else:
            length = stop - start
            if length <= 0:
                new_top = 0
            else:
                if base_top is None:
                    new_top = length
                else:
                    new_top = max(min(length, max(base_top - start, 0)), 0)

        p["$skip"] = str(new_skip)
        if new_top is not None:
            p["$top"] = str(new_top)
        # else: leave $top unset (don’t force it)

        return self._clone(params=p)

    def filter(self, *q: Q, **lookups: Any) -> QuerySet[TModel]:
        self._check_capability("filter")
        new_q = self._q

        # positional Q objects
        for qobj in q:
            new_q = qobj if new_q is None else (new_q & qobj)

        # kwargs -> implicit Q
        if lookups:
            kw_q = Q(**lookups)
            new_q = kw_q if new_q is None else (new_q & kw_q)

        return self._clone(q=new_q)

    def only(self, *fields: str) -> QuerySet[TModel]:
        graph_fields = [self.model._meta.field_to_graph(f) for f in fields]
        p = dict(self._params)
        p["$select"] = ",".join(graph_fields)
        return self._clone(params=p)

    # def select_related(self, *fields: str) -> QuerySet[TModel]:
    #     graph_fields = [self.model._meta.field_to_graph(f) for f in fields]
    #     p = dict(self._params)
    #     p["$select"] = ",".join(graph_fields)
    #     return self._clone(params=p)

    def order_by(self, *fields: str) -> QuerySet[TModel]:
        self._check_capability("order_by")
        parts: list[str] = []
        for item in fields:
            desc = item.startswith("-")
            py_name = item[1:] if desc else item
            gf = self.model._meta.field_to_graph(py_name)
            parts.append(f"{gf} desc" if desc else gf)
        p = dict(self._params)
        p["$orderby"] = ",".join(parts)
        return self._clone(params=p)

    # def top(self, n: int) -> QuerySet[TModel]:
    #     p = dict(self._params)
    #     p["$top"] = int(n)
    #     return self._clone(params=p)

    def count(self) -> QuerySet[TModel]:
        # $count typically requires ConsistencyLevel: eventual
        p = dict(self._params)
        p["$count"] = "true"
        h = dict(self._headers)
        h["ConsistencyLevel"] = "eventual"
        return self._clone(params=p, headers=h)

    def first(self) -> TModel | None:
        for obj in self[:1]:
            return obj
        return None

    def get(self, *, id: str | None = None, **lookups: Any) -> TModel:
        if id:
            m = self.model
            return m.from_graph(
                m._get_client().get(
                    f"{m.endpoint}/{id}",
                    params=self._params,
                    headers=self._headers,
                )
            )
        objs = list(self.filter(**lookups)[:2])
        if not objs:
            raise LookupError("DoesNotExist")
        if len(objs) > 1:
            raise LookupError("MultipleObjectsReturned")
        return objs[0]

    def create(self, **kwargs: Any) -> TModel:
        obj = self.model(**kwargs)
        obj.save()
        return obj

    def _clone(
        self,
        *,
        q: Q | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> QuerySet[TModel]:

        return self.__class__(
            self.model,
            q=q or self._q,
            params=dict(self._params) if params is None else params,
            headers=dict(self._headers) if headers is None else headers,
            **dict(self._kwargs),
        )

    def _compile_q(self, q: Q) -> str:
        def compile_node(node: Node) -> str:
            if isinstance(node, Q):
                inner = f" {node.op.lower()} ".join(
                    compile_node(c) for c in node.children
                )
                return f"({inner})"

            field_name, value, lookup = node
            gf = self.model._meta.field_to_graph(field_name)
            return compile_lookup(gf, lookup, value)

        return compile_node(q)

    def _build_params(self) -> dict[str, Any]:
        p = dict(self._params)
        parts: list[str] = []
        if self._q is not None:
            parts.append(self._compile_q(self._q))
        if parts:
            p["$filter"] = " and ".join(parts)
        return p

    def _check_capability(self, name: str) -> None:
        if not getattr(self.model.capabilities, name, False):
            raise ValueError(f"{self.model.__name__} does not support {name}()")


class QuerySetBulkOperation:

    def __init__(self, qs):
        self.qs = qs

    def get_ids(self, attr="id") -> list[str]:
        ids: list[str] = []
        seen: set[str] = set()

        for item in self.qs.only(attr):
            item_id = getattr(item, attr)  # Let it raise KeyError
            if item_id not in seen:
                seen.add(item_id)
                ids.append(item_id)

        return ids

    @classmethod
    def as_descriptor(cls):
        return QuerySetDescriptor(cls)


class QuerySetDescriptor:
    def __init__(self, klass: type["QuerySetBulkOperation"]):
        self.klass = klass

    def __get__(self, obj: QuerySet, objtype=None) -> QuerySetBulkOperation:
        if obj is None:
            return self
        return self.klass(obj)
