from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Generic, cast

from pymsgraph.models.base import Model, TModel
from pymsgraph.utils import get_model_class

if TYPE_CHECKING:
    from pymsgraph.client import Client


Lookup = tuple[str, Any, str]  # (field_name, value, lookup)


PY_TO_ODATA_LITERAL: dict[str, Any] = {
    "bool": lambda x: str(x).lower(),
    "nonetype": "null",
    "int": lambda x: str(x),
    "float": lambda x: str(x),
    "str": lambda x: "'" + x.replace("'", "''") + "'",
}


def in_lookup(field, value):
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise TypeError("__in expects a non-string iterable")
    parts = [f"{field} eq {odata_literal(v)}" for v in value]
    return "(" + " or ".join(parts) + ")" if parts else "(false)"


PY_LOOKUP_TO_ODATA_QUERY: dict[str, Any] = {
    "exact": lambda gf, v,: f"{gf} eq {odata_literal(v)}",
    "ne": lambda gf, v: f"{gf} ne {odata_literal(v)}",
    "gt": lambda gf, v: f"{gf} gt {odata_literal(v)}",
    "gte": lambda gf, v: f"{gf} ge {odata_literal(v)}",
    "lt": lambda gf, v: f"{gf} lt {odata_literal(v)}",
    "lte": lambda gf, v: f"{gf} le {odata_literal(v)}",
    "contains": lambda gf, v: f"contains({gf}, {odata_literal(v)})",
    "startswith": lambda gf, v: f"startswith({gf}, {odata_literal(v)})",
    "endswith": lambda gf, v: f"endswith({gf}, {odata_literal(v)})",
    "isnull": lambda gf, v: f"{gf} eq null" if v else f"{gf} ne null",
    "in": in_lookup,
}


def odata_literal(value: Any) -> str:
    _type = type(value).__name__.lower()
    try:
        func = PY_TO_ODATA_LITERAL[_type]
    except KeyError:
        raise TypeError(f"Unsupported literal type: {type(value)!r}") from None
    return func(value)


def compile_lookup(graph_field: str, lookup: str, value: Any) -> str:
    lookup = lookup or "exact"
    try:
        func = PY_LOOKUP_TO_ODATA_QUERY[lookup]
    except:
        raise ValueError(f"Unsupported lookup: {lookup!r}") from None
    return func(graph_field, value)


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


@dataclass(frozen=True)
class Capabilities:
    filter: bool
    search: bool
    order_by: bool
    count: bool
    top: bool
    first: bool
    expand: bool
    select: bool
    create: bool
    get: bool

    @classmethod
    def read_write(
        cls,
        filter: bool = True,
        search: bool = False,
        order_by: bool = True,
        count: bool = True,
        top: bool = True,
        first: bool = True,
        expand: bool = True,
        select: bool = True,
        create: bool = True,
        get: bool = True,
    ) -> Capabilities:
        return cls(
            filter, search, order_by, count, top, first, expand, select, create, get
        )

    @classmethod
    def read_only(
        cls,
        filter: bool = False,
        search: bool = False,
        order_by: bool = False,
        count: bool = False,
        top: bool = False,
        first: bool = False,
        expand: bool = True,
        select: bool = True,
        create: bool = False,
        get: bool = False,
    ) -> Capabilities:
        return cls(
            filter, search, order_by, count, top, first, expand, select, create, get
        )


class ModelDescriptor:
    def __init__(self, model_class: type[Model] | str | None = None):
        self.model_class = model_class

    def __get__(self, obj: QuerySet[TModel], objtype=None) -> type[Model]:
        if obj is None:
            return self.model_class

        if isinstance(self.model_class, str):
            return get_model_class(self.model_class)

        model_class = obj._model_class or self.model_class
        if model_class is None:
            raise RuntimeError(
                "Model class must set in the QuerySet class or passing it when initializing a QuerySet"
            )

        return model_class


class EndpointDescriptor:
    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint

    def __get__(self, obj: QuerySet[TModel], objtype=None) -> str:
        if obj is None:
            return self.endpoint
        ep = self.endpoint
        mc_ep = obj.model_class.endpoint
        if parent_ep := getattr(obj._parent, "endpoint", None):
            if ep:
                return f"{parent_ep}{ep}"
            if mc_ep:
                return f"{parent_ep}{mc_ep}"
            return parent_ep
        if mc_ep:
            if ep:
                return f"{mc_ep}{ep}"
            return mc_ep
        if ep:
            return ep
        raise RuntimeError("No endpoint found.")


class QuerySetBase(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]):
        cls = super().__new__(mcls, name, bases, attrs)

        for base in bases:
            if base.__name__ == "QuerySet":
                setattr(cls, "model_class", ModelDescriptor(attrs.get("model_class")))
                setattr(cls, "endpoint", EndpointDescriptor(attrs.get("endpoint")))
        return cls


class Collection:
    pass


class QuerySet(Generic[TModel], metaclass=QuerySetBase):

    capabilities: ClassVar[Capabilities] = Capabilities.read_only()
    search_field: ClassVar[str]
    related_lookup: ClassVar[dict[str, Callable]] = {}
    model_class: type[TModel]
    endpoint: ClassVar[str]

    def __init__(
        self,
        client: "Client | None" = None,
        *,
        model_class: type[TModel] | str | None = None,  # type: ignore
        parent: Model | QuerySet[Any] | None = None,
        q: Q | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        if isinstance(model_class, str):
            model_class = cast(type[TModel], get_model_class(model_class))
        self._model_class = model_class
        self._c = client
        self._q = q
        self._params = dict(params) if params else {}
        self._headers = dict(headers) if headers else {}
        self._parent = parent

        self._changed: bool = True
        self._data: dict[str, Any] = {}
        self._next_link: str | None = None
        self._fetched: list[dict[str, Any]] = []
        self._objects: list[TModel] = []
        self._count: int = 0

    def __iter__(self) -> Iterator[TModel]:
        client = self._client
        if self._changed:
            data = client.get(
                self.endpoint, params=self._build_params(), headers=self._headers
            )
            self._next_link = data.get("@odata.nextLink")
            self._count = data.get("@odata.count", 0)
            self._changed = False
            for obj in self._iter_objects(data):
                self._objects.append(obj)
                yield obj
        else:
            for obj in self._objects:
                yield obj

    def all(self) -> Iterator[TModel]:
        """
        Iterate over all items, fetching nextLink, if any.
        """
        yield from self.__iter__()
        while self._next_link:
            iter_next_objects = self.iter_next_objects()
            if iter_next_objects is None:
                break
            yield from iter_next_objects

    def iter_next_objects(self) -> Iterator[TModel] | None:
        """
        Fetch the nextLink if available and return its items as models.
        """
        if not self._next_link:
            return

        path = self._next_link
        base = getattr(self._client, "base_url", "")
        if base and path.startswith(base):
            path = path[len(base) :]
        path = path.lstrip("/")

        data = self._client.get(path, headers=self._headers)
        self._data = data
        self._next_link = data.get("@odata.nextLink")
        # self._count = data.get("@odata.count", 0)

        for obj in self._iter_objects(data.get("value", [])):
            self._objects.append(obj)
            yield obj
        # for item in :
        #     obj = self.model_class(graph_data=item, parent=self)
        #     yield obj

    def has_next_objects(self) -> bool:
        """
        Return True if there is a nextLink available to fetch more items.
        """
        return self._next_link is not None

    # def __getitem__(self, key: slice | int) -> "QuerySet[TModel]":
    #     if isinstance(key, int):
    #         # Optional: Django-style would execute and return an item.
    #         # For a purely-lazy QuerySet, returning a sliced QuerySet is simplest:
    #         if key < 0:
    #             raise IndexError(
    #                 "Negative indexes are not supported for Graph querysets."
    #             )
    #         return self[key : key + 1]

    #     if key.step not in (None, 1):
    #         raise TypeError("Slicing with a step is not supported (use [:N] or [A:B]).")

    #     start = 0 if key.start is None else key.start
    #     stop = key.stop

    #     if start < 0 or (stop is not None and stop < 0):
    #         raise IndexError("Negative slicing is not supported for Graph querysets.")

    #     p = dict(self._params or {})

    #     # read existing paging state (if any)
    #     base_skip = int(p.get("$skip", 0) or 0)
    #     base_top = int(p["$top"]) if "$top" in p and p["$top"] is not None else None

    #     # new skip is relative to existing skip
    #     new_skip = base_skip + start

    #     # compute new top (limit)
    #     if stop is None:
    #         new_top = None if base_top is None else max(base_top - start, 0)
    #     else:
    #         length = stop - start
    #         if length <= 0:
    #             new_top = 0
    #         else:
    #             if base_top is None:
    #                 new_top = length
    #             else:
    #                 new_top = max(min(length, max(base_top - start, 0)), 0)

    #     p["$skip"] = str(new_skip)
    #     if new_top is not None:
    #         p["$top"] = str(new_top)
    #     # else: leave $top unset (don’t force it)

    #     return self._make_clone(params=p)

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

        return self._make_clone(q=new_q)

    def search(self, keyword: str) -> QuerySet[TModel]:
        self._check_capability("search")
        search_field = getattr(self.model_class, "search_field", None)
        if search_field:
            # p = self._params
            graph_field = self.model_class._meta.field_to_graph(search_field)
            print(graph_field)
            if not graph_field:
                raise ValueError(
                    f"Field not exist in {self.model_class.__name__} property, '{search_field}'"
                )
            self._params["$search"] = f'"{graph_field}:{keyword}"'
            return self._make_clone()
        raise ValueError(f"Object {self.model_class.__name__} does not support search")

    def expand(
        self, field: str, *, select: Iterable[str] | None = None
    ) -> QuerySet[TModel]:
        self._check_capability("expand")
        if select is not None:
            val = f"{field}(select={','.join(select)})"
        else:
            val = field
        current_val = self._params.get("$expand")
        if current_val:
            val = f"{current_val},{val}"
        self._params["$expand"] = val
        return self._make_clone()

    def select(self, *fields: str) -> QuerySet[TModel]:
        self._check_capability("select")
        if not fields:
            return self
        graph_fields = [self.model_class._meta.field_to_graph(f) for f in fields]
        # p = dict(self._params)
        self._params["$select"] = ",".join(graph_fields)
        return self._make_clone()

    # def select_related(self, *fields: str) -> QuerySet[TModel]:
    #     graph_fields = [self.model._meta.field_to_graph(f) for f in fields]
    #     p = dict(self._params)
    #     p["$select"] = ",".join(graph_fields)
    #     return self._make_clone(params=p)

    def order_by(self, *fields: str) -> QuerySet[TModel]:
        self._check_capability("order_by")
        parts: list[str] = []
        for item in fields:
            desc = item.startswith("-")
            py_name = item[1:] if desc else item
            gf = self.model_class._meta.field_to_graph(py_name)
            parts.append(f"{gf} desc" if desc else gf)
        # p = dict(self._params)
        self._params["$orderby"] = ",".join(parts)
        return self._make_clone()

    def top(self, n: int) -> QuerySet[TModel]:
        self._check_capability("top")
        # p = dict(self._params)
        self._params["$top"] = int(n)
        return self._make_clone()

    def count(self) -> int:
        # self._check_capability("count")
        if self._count:
            return self._count

        if self._changed:
            self._params["$count"] = "true"
            self.set_consistency_level_to_eventual()
            list(self)
            return self._count

        return len(self._objects)

    def first(self) -> TModel | None:
        self._check_capability("first")
        for obj in self.top(1):
            return obj
        return None

    def get(self, *, id: str | None = None, **lookups: Any) -> TModel:
        self._check_capability("get")
        if id:
            data = self._client.get(
                f"{self.endpoint}/{id}", params=self._params, headers=self._headers
            )
            if data:
                return self.model_class(graph_data=data, parent=self)
            raise RuntimeError(f"No resource ({self.model_class.__name__}) found, {id}")
        if not lookups:
            raise ValueError(f"{type(self)}.get requires id= or filters")
        objs = list(self.filter(**lookups).top(2))
        if not objs:
            raise RuntimeError(f"No resource ({self.model_class.__name__}) found, {id}")
        if len(objs) > 1:
            raise RuntimeError(
                f"Multiple resources found. Use filter method instead, {lookups} "
            )
        return objs[0]

    def create(self, **kwargs: Any) -> TModel:
        self._check_capability("create")
        obj = self.model_class(**kwargs, parent=self)
        obj._validate_for_create()
        obj = self.model_class(client=self._client, **kwargs)
        payload = obj.to_graph(for_update=False)
        graph_data = self._client.post(self.endpoint, json_body=payload)
        obj.refresh_from_graph(graph_data)
        return obj

    def set_consistency_level_to_eventual(self) -> "QuerySet":
        self._headers["ConsistencyLevel"] = "eventual"
        return self

    def _make_clone(self, *, q: Q | None = None) -> QuerySet[TModel]:
        return self.__class__(
            client=self._c,
            model_class=self.model_class,
            parent=self._parent,
            q=q or self._q,
            params=self._params,
            headers=self._headers,
        )

    def _compile_q(self, q: Q) -> str:
        def compile_node(node: Node) -> str:
            if isinstance(node, Q):
                inner = f" {node.op.lower()} ".join(
                    compile_node(c) for c in node.children
                )
                return f"({inner})"

            field_name, value, lookup = node
            meta = self.model_class._meta
            # print(field_name, value, lookup)
            related_lookup = self.related_lookup.get(field_name)
            if related_lookup is not None:
                return related_lookup(lookup or "exact", value)

            gf = meta.field_to_graph(field_name)
            # validate lookup support if model declares it

            lookups = getattr(meta.fields.get(field_name), "supported_lookups", None)
            if lookups:
                # allowed = supported.get(field_name)
                normalized = lookup or "exact"
                if normalized not in lookups:
                    raise ValueError(
                        f"Lookup '{normalized}' is not supported for field '{field_name}'"
                    )
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
        if not getattr(self.capabilities, name, False):
            raise ValueError(f"{self.__class__.__name__} does not support {name}()")

    def _iter_objects(self, data: dict[str, Any]) -> Iterator[TModel]:
        for item in data.get("value", []):
            yield self.model_class(graph_data=item, parent=self)

    def _get_object(self) -> Model:
        obj = getattr(self, "_obj", None)
        if not obj:
            raise ValueError("No object found for this queryset.")
        return obj

    @property
    def _client(self) -> "Client":
        if c := self._c or getattr(self._parent, "_client", None):
            return c
        raise RuntimeError("No client found.")

    def make_from_graph(self, data: dict[str, Any]):
        return self.model_class(graph_data=data, parent=self)

    def make(self, **kwargs: Any):
        return self.model_class(**kwargs, parent=self)


class BulkQuerySet:
    def __init__(self, queryset: QuerySet[TModel], endpoint: str | None = None) -> None:
        self._queryset = queryset
        self._client = queryset._client
        self._endpoint = endpoint or self._queryset.endpoint
