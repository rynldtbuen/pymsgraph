from __future__ import annotations

import asyncio
from dataclasses import field
from datetime import date, datetime, timezone
import re
from collections.abc import AsyncIterator, Callable, Collection, Iterable
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Collection, Generic, Iterator, Self, TypeVar

from pymsgraph import utils
from pymsgraph.utils import to_camel_case

if TYPE_CHECKING:
    from pathlib import Path

    from pymsgraph.client import Client
    from pymsgraph.models.base import Model

__all__ = ["QuerySet", "Q"]

_Tm = TypeVar("_Tm", bound="Model")


class QuerySet(Generic[_Tm]):
    PATH: str | None = None
    model_class: type[_Tm] | None = None
    page_size: int | None = 50

    def __init__(
        self,
        client: "Client | None" = None,
        *,
        path: str | None = None,
        model_class: "type[Model] | None" = None,
        **kwargs: Any,
    ) -> None:
        model_class = model_class or self.model_class
        self._args: tuple[Any, ...] = (
            client,
            path or getattr(model_class, "PATH", None),
            model_class,
        )
        self._params: dict[str, Any] = {}
        self._headers: dict[str, Any] = {}

        self._paginator: Paginator[_Tm] | None = None
        self._all: bool = False
        self._kwargs: dict[str, Any] = kwargs
        self._seeded_objects: list[_Tm] | None = None

    @property
    def path(self) -> str:
        if e := self._args[1]:
            return e
        raise AttributeError(f"{type(self).__name__} object has no attribute 'path'")

    def filter(self, *q_objects: "Q", **kwargs: Any) -> Self:
        if not q_objects and not kwargs:
            return self

        qs = self._clone()
        expressions: list[str] = qs._params.setdefault("$filter", [])

        for q_obj in q_objects:
            if (expr := q_obj.to_odata_query()) not in expressions:
                expressions.append(expr)
        for key, value in kwargs.items():
            expr = qs._compile_filter_expr(key, value)
            if expr not in expressions:
                expressions.append(expr)

        return qs

    def exclude(self, *q_objects: "Q", **kwargs: Any) -> Self:
        if not q_objects and not kwargs:
            return self

        qs = self._clone()
        expressions: list[str] = qs._params.setdefault("$filter", [])

        for q_obj in q_objects:
            expr = f"not ({q_obj.to_odata_query()})"
            if expr not in expressions:
                expressions.append(expr)
        for key, value in kwargs.items():
            expr = f"not ({qs._compile_filter_expr(key, value)})"
            if expr not in expressions:
                expressions.append(expr)

        return qs

    def select(self, *args: str) -> Self:
        if not args:
            return self

        qs = self._clone()
        selected_fields = qs._params.setdefault("$select", [])

        for field in args:
            if field not in selected_fields:
                selected_fields.append(field)

        return qs

    def order_by(self, *fields: str) -> Self:
        if not fields:
            return self

        qs = self._clone()
        expressions = qs._params.setdefault("$orderby", [])

        for field in fields:
            normalized = field[1:] if field.startswith("-") else field
            if (field_obj := self._model_class.FIELDS.get(normalized)) is None:
                raise ValueError(f"Unkown field: {normalized!r}")
            elif not field_obj.order_by:
                raise ValueError(f"Unsupported order_by field: {normalized!r}")
            expr = (field,)
            if field.startswith("-"):
                expr = (field[1:], "desc")
            if expr not in expressions:
                expressions.append(expr)

        return qs

    def search(self, *q_objects: "Q", **kwargs: Any) -> Self:
        if not q_objects and not kwargs:
            return self

        if not getattr(self._model_class, "SEARCH_FIELD", None):
            raise ValueError(f"{self._model_class.__name__} does not support search")

        qs = self._clone()
        values = qs._params.setdefault("$search", [])

        for q_obj in q_objects:
            if (expr := q_obj.to_search_format()) not in values:
                values.append(expr)
        for k, v in kwargs.items():
            val = f'"{to_camel_case(k)}:{v}"'
            if val not in values:
                values.append(val)

        return qs

    def top(self, value: int) -> Self:
        if value < 1:
            raise ValueError("value must be greater than zero.")
        qs = self._clone()
        qs._params["$top"] = value
        return qs

    def expand(self, field: str, *select: str) -> Self:
        qs = self._clone()
        expands: dict[str, set[str]] = qs._params.setdefault("$expand", {})
        explicit_select = bool(select)
        if field_obj := qs._model_class.FIELDS.get(field):
            if not field_obj.expand:
                raise ValueError(f"Field {field!r} does not support expand")
            graph_field = field_obj.graph_attr_name or to_camel_case(field)
            model_class: type[Model] | None = getattr(field_obj, "model_class", None)
            if not select and model_class is not None:
                defaults = model_class.DEFAULT_SELECT_FIELDS
                if defaults:
                    select = tuple(defaults)
        else:
            raise ValueError(f"Unknown field {field!r}")
        if graph_field not in expands:
            expands[graph_field] = set()
        if select:
            selects = {to_camel_case(s) for s in select}
            if explicit_select and "id" not in selects:
                selects.add("id")
            expands[graph_field].update(selects)
        return qs

    def all(self) -> Self:
        """Return a copy of the queryset"""
        qs = self._clone()
        qs._all = True
        return qs

    def with_count(self) -> Self:
        qs = self._clone()
        qs._params["$count"] = "true"
        return qs.with_consistency_level_eventual()

    def with_consistency_level_eventual(self) -> Self:
        qs = self._clone()
        qs._headers["ConsistencyLevel"] = "eventual"
        return qs

    def prefetch(self, *fields: str) -> "QuerySet[_Tm]":
        if not fields:
            return self

        from pymsgraph.models.fields import QuerySetField

        qs = self._clone()
        prefetch_fields = set(qs._kwargs.get("prefetch", []))
        for name in fields:
            field_obj = self._model_class.FIELDS.get(name)
            if field_obj is None:
                raise ValueError(f"Unknown field {name!r}")
            if not isinstance(field_obj, QuerySetField):
                raise ValueError(f"{name!r} is not a related QuerySetField")
            if not field_obj.prefetch:
                raise ValueError(f"{name!r} does not support prefetch")
            if name not in prefetch_fields:
                prefetch_fields.add(name)
        qs._kwargs["prefetch"] = prefetch_fields
        return qs

    def iterator(self, *, page_size: int | None = None) -> "Paginator[_Tm]":
        if self._seeded_objects is not None:
            raise ValueError("Paginator is not available for seeded querysets")
        if (p := self._paginator) is None:
            # ctx = Context.make(self._ctx, queryset=self)
            p = Paginator[_Tm](self, page_size=page_size or self.page_size)
            self._paginator = p
        return p

    async def exists(self) -> bool:
        return bool(await self.count())

    async def count(self) -> int | None:
        return await self.iterator().count()

    async def get(self, id: str | None = None, **kwargs) -> _Tm:
        if id:
            data = await self._client.get(
                f"{self.path}/{id}", params=self._build_params()
            )
            return self.make_from_graph(data)

        if not kwargs:
            raise ValueError("No kwargs found.")

        results = [o async for o in self.filter(**kwargs).top(2)]

        if not results:
            raise DoesNotExist(
                f"{self._model_class.__name__} matching query does not exist"
            )

        if len(results) > 1:
            raise MultipleObjectsReturned(
                f"get() returned more than one {self._model_class.__name__}"
            )

        return results[0]

    async def first(self) -> _Tm | None:
        async for obj in self.top(1):
            return obj
        return None

    async def create(self, **kwargs: Any) -> _Tm:
        if self._model_class.READ_ONLY:
            raise ValueError(f"{self._model_class.__name__} is read-only")
        obj = self._model_class(client=self._client, path=self.path, **kwargs)
        obj._validate_for_create()
        data = await self._client.post(self.path, body=obj.serialize())
        return self._model_class.from_graph(data, client=self._client, path=self.path)

    async def update(self, **fields: Any) -> int:
        """
        Bulk update all objects in this queryset.

        Returns the number of objects updated.
        """
        if self._model_class.READ_ONLY:
            raise ValueError(f"{self._model_class.__name__} is read-only")
        if not fields:
            return 0

        # Validate fields
        payload: dict[str, Any] = {}
        for attr_name, val in fields.items():
            field_obj = self._model_class.FIELDS.get(attr_name)
            if field_obj is None:
                raise ValueError(f"Unknown field {attr_name!r}")
            if field_obj.read_only:
                raise ValueError(f"Field {attr_name!r} is read-only")
            graph_name = field_obj.graph_attr_name or to_camel_case(attr_name)
            payload[graph_name] = field_obj.to_graph(val)

        total_updated = 0
        batch_size = 20

        async for batch in utils.achunks(self.select("id"), batch_size):
            await self._bulk_patch(batch, payload)
            total_updated += len(batch)

        return total_updated

    async def values(self, *fieldnames: str) -> list[dict[str, Any]]:
        """
        Return a list of dicts for selected fieldnames.
        """

        def _coerce(val: Any) -> Any:
            if isinstance(val, Model):
                return val.to_dict()
            if isinstance(val, list):
                return [_coerce(v) for v in val]
            if isinstance(val, dict):
                return {k: _coerce(v) for k, v in val.items()}
            return val

        fieldnames = fieldnames or self._model_class.DEFAULT_SELECT_FIELDS or tuple()
        if not fieldnames:
            if (default_fieldnames := self._model_class.DEFAULT_SELECT_FIELDS) is None:
                return [
                    {k: _coerce(getattr(o, k)) for k in o._data.keys()}
                    async for o in self.iterator().all()
                ]
            return [
                {k: _coerce(getattr(o, k)) for k in default_fieldnames}
                async for o in self.iterator().all()
            ]

        valid_fields: list[str] = []
        for name in fieldnames:
            if name not in self._model_class.FIELDS:
                raise ValueError(f"Unknown field {name!r}")
            valid_fields.append(name)

        selected = set(self._params.get("$select", []))
        if selected and selected.issuperset(valid_fields):
            objects = self.iterator().all()
        else:
            objects = self.select(*valid_fields).all()

        return [
            {name: _coerce(getattr(o, name)) for name in valid_fields}
            async for o in objects
        ]

    def apply(self, predicate: Callable[[_Tm], bool]) -> AsyncIterator[_Tm]:
        if predicate is None:
            raise ValueError(
                f"{type(self).__name__ } apply requires a callable predicate"
            )

        async def _iter() -> AsyncIterator[_Tm]:
            async for obj in self.iterator().all():
                if predicate(obj):
                    yield obj

        return _iter()

    async def to_csv(
        self,
        path: str | Path,
        *,
        fieldnames: Collection[str] | None = None,
    ) -> None:
        import csv
        import json
        from pathlib import Path

        if fieldnames is not None and len(fieldnames) == 0:
            fieldnames = None
        fieldnames = fieldnames or self._model_class.DEFAULT_SELECT_FIELDS or None
        if fieldnames is None:
            values = await self.values()
        else:
            values = await self.values(*fieldnames)

        if fieldnames is None:
            ordered: list[str] = []
            for row in values:
                for key in row.keys():
                    if key not in ordered:
                        ordered.append(key)
            fieldnames = tuple(ordered)

        out_path = Path(path)
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()

            for val in values:
                row: dict[str, Any] = {}
                for k, v in val.items():
                    if isinstance(v, Model):
                        v = v.to_dict()
                    if isinstance(v, (dict, list)):
                        v = json.dumps(v, ensure_ascii=True)
                    row[k] = v
                writer.writerow(row)

    async def to_dataframe(self, *fieldnames: str):
        import pandas as pd

        fieldnames = fieldnames or self._model_class.DEFAULT_SELECT_FIELDS or tuple()
        if fieldnames:
            values = await self.values()
        else:
            values = await self.values()
        return pd.DataFrame(values)

    def with_objects(
        self,
        *args: str | _Tm | "QuerySet[_Tm]",
        key: str = "id",
    ) -> Self:
        qs = self.__class__(self._client, path=self.path, model_class=self._model_class)
        objects = list(qs._coerce_objects(args, key=key))
        if not objects:
            return qs

        qs._seeded_objects = objects
        return qs

    def make(self, **kwargs: Any) -> _Tm:
        return self._model_class(**kwargs, client=self._client, path=self.path)

    def make_from_graph(self, data: dict[str, Any]):
        return self._model_class.from_graph(data, client=self._client, path=self.path)

    def __aiter__(self) -> AsyncIterator[_Tm]:
        """Execute the query and fetch results"""
        if self._seeded_objects is not None:

            async def _iter_seeded() -> AsyncIterator[_Tm]:
                for obj in self._seeded_objects or []:
                    yield obj

            return _iter_seeded()
        paginator = self.iterator()
        if not self._all:
            return paginator._fetch_page(1)
        return paginator.all()

    @property
    def _client(self) -> "Client":
        if c := self._args[0]:
            return c
        raise AttributeError(f"{type(self).__name__} object has no attribute '_client'")

    @property
    def _model_class(self) -> type[_Tm]:
        if c := self._args[2]:
            return c
        raise AttributeError(
            f"{type(self).__name__} object has no attribute '_model_class'"
        )

    async def _bulk_patch(self, iterable: list[_Tm], payload: dict[str, Any]) -> None:
        requests: list[dict[str, Any]] = []
        for i, obj in enumerate(iterable, start=1):
            requests.append(
                {
                    "id": str(i),
                    "method": "PATCH",
                    "url": obj.path,
                    "headers": {"Content-Type": "application/json"},
                    "body": payload,
                }
            )

        resp = await self._client.post("/$batch", body={"requests": requests})
        try:
            from pymsgraph import utils

            utils.raise_batch_errors(resp, action="bulk update")
        except Exception:
            # rethrow original error for clarity
            raise

    async def _prefetch_related(self, objects: list[_Tm], fields: list[str]) -> None:
        if not objects or not fields:
            return

        requests: list[dict[str, Any]] = []
        mapping: dict[str, tuple[_Tm, str]] = {}
        req_id = 1

        for obj in objects:
            for field_name in fields:
                qs = getattr(obj, field_name)
                if not hasattr(qs, "path"):
                    continue
                req_id_str = str(req_id)
                requests.append(
                    {
                        "id": req_id_str,
                        "method": "GET",
                        "url": qs.path,
                    }
                )
                mapping[req_id_str] = (obj, field_name)
                req_id += 1

        for chunk in utils.chunks(requests, 20):
            resp = await self._client.post("/$batch", body={"requests": chunk})
            utils.raise_batch_errors(resp, action="prefetch related")
            for r in resp.get("responses", []) or []:
                rid = str(r.get("id"))
                obj_field = mapping.get(rid)
                if not obj_field:
                    continue
                obj, field_name = obj_field
                body = r.get("body") or {}
                obj._data[field_name] = body.get("value", [])
                if hasattr(obj, "_prefetch_meta"):
                    obj._prefetch_meta[field_name] = {
                        "next_link": body.get("@odata.nextLink"),
                        "count": body.get("@odata.count"),
                    }

    def _clone(self) -> Self:
        obj = self.__class__(
            self._client, path=self.path, model_class=self._model_class
        )
        obj._params = deepcopy(self._params)
        obj._headers = dict(self._headers)
        obj._kwargs = dict(self._kwargs)
        obj._all = self._all
        if self._seeded_objects is not None:
            obj._seeded_objects = list(self._seeded_objects)
        return obj

    def _compile_filter_expr(self, key: str, value: Any) -> str:
        if "__" in key:
            field, lookup = key.split("__", 1)
        else:
            field, lookup = key, "exact"

        field_obj = self._model_class.FIELDS.get(field) if self._model_class else None
        from pymsgraph.models import fields as _fields

        if isinstance(field_obj, _fields.ListField):
            graph_field = field_obj.graph_attr_name or to_camel_case(field)
            return compile_list_lookup(graph_field, lookup, value)

        if isinstance(field_obj, _fields.QuerySetField):
            graph_field = field_obj.graph_attr_name or to_camel_case(field)
            if lookup == "isnull":
                return compile_list_lookup(graph_field, "isnull", value)

            model_class = field_obj.model_class or field_obj.queryset_class.model_class
            if model_class is None:
                raise ValueError(f"{field!r} related model is not configured")

            if isinstance(model_class, str):
                from pymsgraph.utils import get_model_class

                model_class = get_model_class(model_class)

            if "__" in lookup:
                element_field, element_lookup = lookup.split("__", 1)
            else:
                element_field, element_lookup = lookup, "exact"

            element = model_class.FIELDS.get(element_field)
            if element is None:
                raise ValueError(
                    f"Unsupported related field: {field}__{element_field!r}"
                )
            element_graph = element.graph_attr_name or to_camel_case(element_field)

            try:
                func = PY_TO_ODATA_QUERY[element_lookup]
            except KeyError:
                raise ValueError(f"Unsupported lookup: {element_lookup!r}") from None

            clause = func(f"u/{element_graph}", value)
            return f"{graph_field}/any(u:{clause})"

        # fallback to scalar compiler
        return to_odata_query(key, value)

    def _build_params(self) -> dict[str, Any]:
        """Build OData query parameters"""
        compiled_params = {}
        params = deepcopy(self._params)

        if values := params.pop("$filter", None):
            compiled_params["$filter"] = " and ".join(f"({v})" for v in values)

        if "$select" not in params:
            default_fields = getattr(self._model_class, "DEFAULT_SELECT_FIELDS", None)
            if default_fields and len(default_fields) > 1:
                params["$select"] = sorted(default_fields)

        if values := params.pop("$select", None):
            if self._model_class.HAS_ID and "id" not in values:
                values = ["id"] + list(values)
            compiled_params["$select"] = ",".join([to_camel_case(v) for v in values])

        if values := params.pop("$orderby", None):
            compiled_params["$orderby"] = ",".join(
                [
                    (
                        to_camel_case(v[0])
                        if len(v) < 2
                        else f"{to_camel_case(v[0])} {v[1]}"
                    )
                    for v in values
                ]
            )

        if values := params.pop("$search", None):
            compiled_params["$search"] = " AND ".join(values)

        if expands := params.pop("$expand", None):
            parts: list[str] = []
            for name, fields in expands.items():
                if fields:
                    parts.append(f"{name}($select={','.join(sorted(fields))})")
                else:
                    parts.append(name)
            compiled_params["$expand"] = ",".join(parts)

        compiled_params.update(params)

        return compiled_params

    async def _iter_objects(self, async_gen: Any) -> list[_Tm]:
        return [i async for i in async_gen]

    def _coerce_objects(
        self, args: tuple[str | _Tm | QuerySet[_Tm], ...], key: str = "id"
    ) -> Iterator[_Tm]:
        def _iter_flatten(iterable) -> Iterator[_Tm]:
            for item in iterable:
                if isinstance(item, str):
                    yield self.make_from_graph(data={key: item})
                elif isinstance(item, self._model_class):
                    yield item
                elif isinstance(item, QuerySet):
                    objects = asyncio.run(self._iter_objects(item))
                    for obj in objects:
                        yield obj
                else:
                    continue

        seen: set[str] = set()

        for obj in _iter_flatten(args):
            try:
                val = getattr(obj, key)
            except AttributeError:
                continue
            if val not in seen:
                yield obj
            seen.add(val)


class Paginator(Generic[_Tm]):
    def __init__(
        self, queryset: QuerySet[_Tm], *, page_size: int | None = None
    ) -> None:
        qs_kwargs = queryset._kwargs
        self._qs_kwargs = qs_kwargs
        self._queryset = queryset

        self._cached_objects: dict[int, list[_Tm]] = {}
        self._cached_count: int | None = qs_kwargs.get("prefetch_count")
        self._page_size = page_size or queryset.page_size
        self._current_page_number: int = 1
        self._next_link: str | None = qs_kwargs.get("prefetch_next_link")

        cached_data = qs_kwargs.get("cached_data")
        if cached_data is not None:
            objects = self._cached_objects.setdefault(1, [])
            for data in cached_data:
                obj = self._queryset.make_from_graph(data)
                objects.append(obj)

    async def next_page(self) -> list[_Tm]:
        next_page = self._current_page_number + 1
        objects = [o async for o in self._fetch_page(next_page)]
        if objects:
            self._current_page_number = next_page
        return objects

    async def count(self) -> int | None:
        if (count := self._cached_count) is None:
            qs = self._queryset.with_consistency_level_eventual()
            params = qs._build_params()
            params.pop("$count", None)
            path = f"{self._queryset.path}/$count"
            count = await self._queryset._client.get(
                path, params=params, headers={**qs._headers, "Accept": "text/plain"}
            )
            self._cached_count = count  # pyright: ignore[reportAttributeAccessIssue]
        return count  # pyright: ignore[reportReturnType]

    async def total_pages(self) -> int | None: ...

    async def has_next(self) -> bool:
        if not self._cached_objects.get(1):
            async for _ in self._fetch_page(1):
                ...
        return bool(self._next_link)

    def __aiter__(self) -> AsyncIterator[_Tm]:
        return self._fetch_page(self._current_page_number)

    async def all(self) -> AsyncIterator[_Tm]:
        page_numbers = sorted(self._cached_objects)

        if not page_numbers:
            async for obj in self._fetch_page(1):
                yield obj
            next_page_number = 2
        else:
            for page_number in page_numbers:
                async for obj in self._fetch_page(page_number):
                    yield obj
            next_page_number = max(page_numbers) + 1

        while self._next_link:
            async for obj in self._fetch_page(next_page_number):
                yield obj
            next_page_number += 1

    async def first_page(self) -> list[_Tm]:
        return [o async for o in self._fetch_page(1)]

    async def _fetch_page(self, page_number: int | None = None) -> AsyncIterator[_Tm]:
        """Fetch a single page of results"""

        if page_number is None:
            page_number = self._current_page_number

        # e.g. page_number = 3, current_page_number = 1
        if page_number > self._current_page_number + 1:
            # $skip and $top not supported at this stage
            raise ValueError(f"Unable to fetch page, {page_number}.")

        if page_number < 1:
            raise ValueError("page_number must be greater than 0.")

        objects = self._cached_objects.get(page_number)
        if objects is not None:
            for obj in objects:
                yield obj
            return

        queryset = self._queryset

        if page_number == 1:
            params = queryset._build_params()
            if params.get("$top") is None and self._page_size is not None:
                params["$top"] = str(self._page_size)

            path = queryset.path
            if (path_func := getattr(queryset, "_get_path", None)) is not None:
                path: str = await path_func()

            response = await queryset._client.get(
                path, params=params, headers=queryset._headers
            )
        else:
            if not self._next_link:
                return
            response = await queryset._client.get(
                url=self._next_link, headers=queryset._headers
            )

        self._next_link = response.get("@odata.nextLink")
        self._cached_count = response.get("@odata.count")
        objects = self._cached_objects.setdefault(page_number, [])

        for data in response.get("value", []):
            obj = queryset.make_from_graph(data)
            objects.append(obj)

        prefetch_fields = self._qs_kwargs.get("prefetch", [])
        if prefetch_fields:
            await queryset._prefetch_related(objects, prefetch_fields)

        for obj in objects:
            yield obj

        # increase _current_page_number only if page_number is greater than.
        # page_number=2, current_page_number=1
        if page_number > self._current_page_number:
            self._current_page_number = page_number


class Q:
    OR = "OR"
    AND = "AND"
    NOT = "NOT"

    def __init__(self, **kwargs):
        self.filters = kwargs
        self.connector = self.AND
        self.negated = False
        self.children: list["Q"] = []

    def __or__(self, other: "Q") -> "Q":
        """Combine with OR: Q(...) | Q(...)"""
        q = Q()
        q.connector = self.OR
        q.children = [self, other]
        return q

    def __and__(self, other: "Q") -> "Q":
        """Combine with AND: Q(...) & Q(...)"""
        q = Q()
        q.connector = self.AND
        q.children = [self, other]
        return q

    def __invert__(self) -> "Q":
        """Negate with NOT: ~Q(...)"""
        q = Q(**self.filters)
        q.negated = not self.negated
        q.children = self.children
        q.connector = self.connector
        return q

    def to_odata_query(self) -> str:
        """Convert Q object to OData filter string"""
        if self.children:
            # Complex Q with children
            child_expressions = [child.to_odata_query() for child in self.children]

            if self.connector == self.OR:
                expr = " or ".join(f"({e})" for e in child_expressions)
            else:  # AND
                expr = " and ".join(f"({e})" for e in child_expressions)

            if self.negated:
                return f"not ({expr})"
            return f"{expr}"

        else:
            # Simple Q with filters
            expressions = []
            for key, value in self.filters.items():
                expressions.append(to_odata_query(key, value))

            if len(expressions) == 1:
                result = expressions[0]
            else:
                result = " and ".join(f"({e})" for e in expressions)

            if self.negated:
                return f"not ({result})"
            return result

    def to_search_format(self) -> Any:
        """Convert Q object to $search query string"""
        if self.children:
            values = [child.to_search_format() for child in self.children]
            expr = f" {self.connector} ".join(values)
            if any(map(lambda x: x.startswith("("), values)):
                return expr
            return f"({expr})"

        expressions = []
        for key, value in self.filters.items():
            expressions.append(f'"{to_camel_case(key)}:{value}"')
        return " AND ".join(expressions)


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")


def _format_datetime_literal(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _str_to_odata_literal(value: str) -> str:
    s = value.strip()
    if _ISO_DATE_RE.match(s):
        return f"{s}T00:00:00Z"
    if _ISO_DATETIME_RE.match(s):
        if s.endswith("Z"):
            return s
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return "'" + s.replace("'", "''") + "'"
        return _format_datetime_literal(dt)
    return "'" + s.replace("'", "''") + "'"


PY_TO_ODATA_LITERAL: dict[str, Any] = {
    "bool": lambda x: str(x).lower(),
    "nonetype": "null",
    "int": lambda x: str(x),
    "float": lambda x: str(x),
    "datetime": _format_datetime_literal,
    "date": lambda x: f"{x.isoformat()}T00:00:00Z",
    "str": _str_to_odata_literal,
}


def in_lookup(field, value):
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise TypeError("__in expects a non-string iterable")
    parts = [f"{field} eq {to_odata_literal(v)}" for v in value]
    return "(" + " or ".join(parts) + ")" if parts else "(false)"


PY_TO_ODATA_QUERY: dict[str, Any] = {
    "exact": lambda f, v: f"{f} eq {to_odata_literal(v)}",
    "ne": lambda f, v: f"{f} ne {to_odata_literal(v)}",
    "gt": lambda f, v: f"{f} gt {to_odata_literal(v)}",
    "gte": lambda f, v: f"{f} ge {to_odata_literal(v)}",
    "lt": lambda f, v: f"{f} lt {to_odata_literal(v)}",
    "lte": lambda f, v: f"{f} le {to_odata_literal(v)}",
    "contains": lambda f, v: f"contains({f}, {to_odata_literal(v)})",
    "startswith": lambda f, v: f"startswith({f}, {to_odata_literal(v)})",
    "endswith": lambda f, v: f"endswith({f}, {to_odata_literal(v)})",
    "isnull": lambda f, v: f"{f} eq null" if v else f"{f} ne null",
    "in": in_lookup,
}


def to_odata_literal(value: Any) -> str:
    _type = type(value).__name__.lower()
    try:
        func = PY_TO_ODATA_LITERAL[_type]
    except KeyError:
        raise TypeError(f"Unsupported literal type: {type(value)!r}") from None
    return func(value)


def to_odata_query(key: str, value: Any) -> str:
    if "__" in key:
        field, lookup = key.split("__", 1)
    else:
        field, lookup = key, "exact"
    graph_field = to_camel_case(field)
    try:
        func = PY_TO_ODATA_QUERY[lookup]
    except:
        raise ValueError(f"Unsupported lookup: {lookup!r}") from None
    return func(graph_field, value)


def compile_list_lookup(
    graph_field: str, lookup: str, value: Any, var: str = "i"
) -> str:
    """
    Compile lookups for list fields into any()/count OData expressions.
    """
    if lookup == "isnull":
        if not isinstance(value, bool):
            raise ValueError(f"isnull expects bool, got {type(value).__name__}")
        return f"{graph_field}/$count eq 0" if value else f"{graph_field}/$count ne 0"

    if lookup == "exact":
        lookup = "exact"

    try:
        func = PY_TO_ODATA_QUERY[lookup]
    except KeyError:
        raise ValueError(f"Unsupported lookup for list field: {lookup!r}") from None

    clause = func(var, value)
    return f"{graph_field}/any({var}:{clause})"


class DoesNotExist(Exception): ...


class MultipleObjectsReturned(Exception): ...
