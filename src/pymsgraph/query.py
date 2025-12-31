from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Generic, cast

from pymsgraph.fields import QuerySetField
from pymsgraph.models.base import Model, TModel
from pymsgraph import utils

if TYPE_CHECKING:
    from pymsgraph.client import Client

logger = logging.getLogger("pymsgraph")


Lookup = tuple[str, Any, str]  # (field_name, value, lookup)


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
            return utils.get_model_class(self.model_class)

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
        setattr(
            cls,
            "model_class",
            ModelDescriptor(
                attrs.get("model_class") or getattr(cls, "model_class", None)
            ),
        )
        setattr(cls, "endpoint", EndpointDescriptor(attrs.get("endpoint")))
        return cls


class QuerySet(Generic[TModel], metaclass=QuerySetBase):

    capabilities: ClassVar[Capabilities] = Capabilities.read_only()
    search_field: ClassVar[str]
    collection_lookup: ClassVar[dict[str, Callable]] = {}
    model_class: type[TModel]
    endpoint: ClassVar[str]

    def __init__(
        self,
        client: "Client | None" = None,
        *,
        model_class: type[TModel] | str | None = None,  # type: ignore
        parent: Model | TModel | QuerySet[Any] | None = None,
        graph_data: dict[str, Any] | None = None,
        q: Q | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        select_related: Iterable[str] | None = None,
        set_values: dict[str, Any] | None = None,
    ) -> None:
        if isinstance(model_class, str):
            model_class = cast(type[TModel], utils.get_model_class(model_class))
        self._model_class = model_class
        self._c = client
        self._q = q
        self._params = dict(params) if params else {}
        self._headers = dict(headers) if headers else {}
        self._parent = parent
        self._graph_data: dict[str, Any] = dict(graph_data or {})
        self._select_related: set[str] = set(select_related or [])
        self._set_values: dict[str, Any] = dict(set_values or {})

        self._changed: bool = True
        self._data: dict[str, Any] = {}
        self._next_link: str | None = None
        self._fetched: list[dict[str, Any]] = []
        self._objects: list[TModel] = []
        self._count: int = 0

    def __iter__(self) -> Iterator[TModel]:
        client = self._client
        if self._changed:
            params = self._build_params()
            logger.debug(
                "QuerySet.__iter__ model=%s endpoint=%s params=%s",
                self.model_class.__name__,
                self.endpoint,
                params,
            )
            data = client.get(self.endpoint, params=params, headers=self._headers)
            self._next_link = data.get("@odata.nextLink")
            self._count = data.get("@odata.count", 0)
            self._changed = False
            objs = list(self._iter_objects(data))
            self._objects.extend(objs)
            if self._select_related:
                self._prefetch_related(objs)
            yield from objs
        else:
            for obj in self._objects:
                yield obj

    def all(self) -> Iterator[TModel]:
        """
        Iterate over all items, fetching nextLink, if any.
        """
        yield from self.__iter__()
        while self._next_link:
            iter_next_objects = self._iter_next_objects()
            if iter_next_objects is None:
                break
            yield from iter_next_objects

    def has_next_link(self) -> bool:
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
        self._params["$select"] = ",".join(graph_fields)
        return self._make_clone()

    def prefetch(self, *fields: str) -> QuerySet[TModel]:
        """
        Prefetch related collections for the current queryset results.
        """
        if not fields:
            return self
        supported = getattr(self.model_class, "prefetch_fields", set())
        for f in fields:
            if f not in supported:
                raise ValueError(
                    f"{self.model_class.__name__} does not support select_related({f!r})"
                )
        clone = self._make_clone()
        clone._select_related = set(self._select_related).union(fields)
        return clone

    def set_attr(self, name: str, value: Any) -> QuerySet[TModel]:
        """
        Stage a field update to be applied to all objects in this queryset.
        """
        field = self.model_class._meta.fields.get(name)
        if not field:
            raise ValueError(f"Unknown field: {name!r}")
        if field.read_only:
            raise ValueError(f"Field '{name}' is read-only")

        clone = self._make_clone()
        clone._set_values = dict(self._set_values)
        clone._set_values[name] = field.to_python(value)
        return clone

    def order_by(self, *fields: str) -> QuerySet[TModel]:
        self._check_capability("order_by")
        parts: list[str] = []
        for item in fields:
            desc = item.startswith("-")
            py_name = item[1:] if desc else item
            gf = self.model_class._meta.field_to_graph(py_name)
            parts.append(f"{gf} desc" if desc else gf)
        self._params["$orderby"] = ",".join(parts)
        return self._make_clone()

    def save(self) -> int:
        """
        Apply staged set_attr updates to all items in this queryset using $batch.
        Returns the number of objects updated.
        """
        if not self._set_values:
            return 0

        meta = self.model_class._meta
        payload: dict[str, Any] = {}
        for name, val in self._set_values.items():
            field = meta.fields.get(name)
            if not field:
                raise ValueError(f"Unknown field: {name!r}")
            if field.read_only:
                raise ValueError(f"Field '{name}' is read-only")
            assert field.graph_name is not None
            payload[field.graph_name] = field.to_graph(val)

        total = 0
        for batch in utils.chunks(self.all(), 20):
            requests: list[dict[str, Any]] = []
            for idx, obj in enumerate(batch, start=1):
                requests.append(
                    {
                        "id": str(idx),
                        "method": "PATCH",
                        "url": obj.endpoint,
                        "headers": {"Content-Type": "application/json"},
                        "body": payload,
                    }
                )
            resp = self._client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="bulk update")
            total += len(batch)
            for obj in batch:
                for name, val in self._set_values.items():
                    obj._data[name] = val
                    obj._dirty.discard(name)
        return total

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

    def to_csv(
        self,
        path: str | Path,
        *,
        fields: Iterable[str] | None = None,
        include_header: bool = True,
        use_graph_names: bool = False,
    ) -> None:
        """
        Export query results to a CSV file.

        `fields` are model field names. If `use_graph_names` is True, CSV headers
        use Graph names instead of Python field names.
        """
        field_names = list(fields) if fields else list(self.model_class._meta.fields)
        headers = [
            self.model_class._meta.field_to_graph(f) if use_graph_names else f
            for f in field_names
        ]

        out_path = Path(path)
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if include_header:
                writer.writerow(headers)
            for obj in self.all():
                row = []
                for f_name in field_names:
                    val = getattr(obj, f_name, None)
                    if isinstance(val, (dict, list)):
                        val = json.dumps(val, ensure_ascii=True)
                    row.append(val)
                writer.writerow(row)

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

    def make_from_graph(self, data: dict[str, Any]) -> TModel:
        return self.model_class(graph_data=data, parent=self)

    def make(self, **kwargs: Any) -> TModel:
        return self.model_class(**kwargs, parent=self)

    def _make_clone(self, *, q: Q | None = None) -> QuerySet[TModel]:
        return self.__class__(
            client=self._c,
            model_class=self.model_class,
            parent=self._parent,
            q=q or self._q,
            params=self._params,
            headers=self._headers,
            select_related=self._select_related,
            set_values=self._set_values,
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
            field = meta.fields.get(field_name)
            if isinstance(field, QuerySetField):
                val = field.queryset_class._collection_any_lookup(
                    lookup or "exact", value
                )
                if val:
                    return val
                raise RuntimeError(
                    "QuerySetField queyset_class must implement a _collection_any_lookup classmethod."
                )

            # print(field_name, value, lookup)
            # collection_lookup = self.collection_lookup.get(field_name)
            # if collection_lookup is not None:s
            #     return collection_lookup(lookup or "exact", value)

            gf = meta.field_to_graph(field_name)
            # validate lookup support if model declares it

            supported_lookup = getattr(self.model_class, "supported_lookup", {})
            lookups = supported_lookup.get(field_name)
            if lookups:
                # allowed = supported.get(field_name)
                normalized = lookup or "exact"
                if normalized not in lookups:
                    raise ValueError(
                        f"Lookup '{normalized}' is not supported for field '{field_name}'"
                    )

            return utils.compile_lookup(gf, lookup, value)

        return compile_node(q)

    def _build_params(self) -> dict[str, Any]:
        p = dict(self._params)
        parts: list[str] = []
        if self._q is not None:
            parts.append(self._compile_q(self._q))
        if parts:
            p["$filter"] = " and ".join(parts)
        logger.debug(
            "QuerySet._build_params model=%s params=%s",
            self.model_class.__name__,
            p,
        )
        return p

    def _check_capability(self, name: str) -> None:
        if not getattr(self.capabilities, name, False):
            raise ValueError(f"{self.__class__.__name__} does not support {name}()")

    def _prefetch_related(self, objs: list[TModel]) -> None:
        return

    def _iter_objects(self, data: dict[str, Any]) -> Iterator[TModel]:
        for item in data.get("value", []):
            yield self.model_class(graph_data=item, parent=self)

    def _iter_next_objects(self) -> Iterator[TModel] | None:
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

        logger.debug(
            "QuerySet._iter_next_objects model=%s next_link=%s",
            self.model_class.__name__,
            self._next_link,
        )
        data = self._client.get(path, headers=self._headers)
        self._data = data
        self._next_link = data.get("@odata.nextLink")
        # self._count = data.get("@odata.count", 0)

        objs = list(self._iter_objects(data))
        self._objects.extend(objs)
        if self._select_related:
            self._prefetch_related(objs)
        yield from objs
        # for item in :
        #     obj = self.model_class(graph_data=item, parent=self)
        #     yield obj

    @property
    def _client(self) -> "Client":
        if c := self._c or getattr(self._parent, "_client", None):
            return c
        raise RuntimeError("No client found.")

    @classmethod
    def _collection_any_lookup(cls, lookup: str, value: str) -> str | None:
        return None


class BulkQuerySet(Generic[TModel]):
    def __init__(self, queryset: QuerySet[TModel], endpoint: str | None = None) -> None:
        self._queryset = queryset
        self._client = queryset._client
        self._endpoint = endpoint or self._queryset.endpoint
