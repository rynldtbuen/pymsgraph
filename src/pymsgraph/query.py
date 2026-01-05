from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pymsgraph.utils import to_camel_case

if TYPE_CHECKING:
    from pymsgraph.client import Client
    from pymsgraph.models.base import Model

TModel = TypeVar("TModel", bound="Model")


class QuerySet(Generic[TModel]):
    PAGE_SIZE = 50

    def __init__(
        self,
        client: "Client",
        model_class: type[TModel],
        endpoint: str | None = None,
    ) -> None:
        self._client = client
        self._model_class = model_class
        self._endpoint = endpoint
        self._params: dict[str, Any] = {}
        self._headers: dict[str, Any] = {}

        self._cache_objects: dict[int, list[TModel]] = {}
        self._count_cache: int | None = None
        self._all: bool = False

    def _clone(self) -> "QuerySet[TModel]":
        obj = self.__class__(self._client, self._model_class, self._endpoint)
        obj._params = deepcopy(self._params)
        obj._headers = dict(self._headers)
        return obj

    def filter(self, *q_objects: "Q", **kwargs: Any) -> "QuerySet[TModel]":
        if not q_objects and not kwargs:
            return self

        qs = self._clone()
        expressions: list[str] = qs._params.setdefault("$filter", [])

        for q_obj in q_objects:
            if (expr := q_obj.to_odata_query()) not in expressions:
                expressions.append(expr)
        for key, value in kwargs.items():
            if (expr := to_odata_query(key, value)) not in expressions:
                expressions.append(expr)

        return qs

    def select(self, *args: str) -> "QuerySet[TModel]":
        if not args:
            return self

        qs = self._clone()
        selected_fields = qs._params.setdefault("$select", [])

        for field in args:
            if field not in selected_fields:
                selected_fields.append(field)

        return qs

    def order_by(self, *args: str) -> "QuerySet[TModel]":
        if not args:
            return self

        qs = self._clone()
        expressions = qs._params.setdefault("$orderby", [])

        for field in args:
            expr = (field,)
            if field.startswith("-"):
                expr = (field[1:], "desc")
            if expr not in expressions:
                expressions.append(expr)

        return qs

    def search(self, *q_objects: "Q", **kwargs: Any) -> "QuerySet[TModel]":
        if not q_objects and not kwargs:
            return self

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

    def top(self, value: int) -> "QuerySet[TModel]":
        if value < 1:
            raise ValueError("value must be greater than zero.")
        qs = self._clone()
        qs._params["$top"] = str(value)
        return qs

    def expand(self, field: str, *select: str) -> "QuerySet[TModel]":
        qs = self._clone()
        expands: dict[str, set[str]] = qs._params.setdefault("$expand", {})
        graph_field = to_camel_case(field)
        if graph_field not in expands:
            expands[graph_field] = set()
        if select:
            expands[graph_field].update(to_camel_case(s) for s in select)
        return qs

    def all(self) -> "QuerySet[TModel]":
        """Return a copy of the queryset"""
        qs = self._clone()
        qs._all = True
        return qs

    def with_count(self) -> QuerySet[TModel]:
        qs = self.with_consistency_level_eventual()
        qs._params["$count"] = "true"
        return qs

    def with_consistency_level_eventual(self):
        qs = self._clone()
        qs._headers["ConsistencyLevel"] = "eventual"
        return qs

    def prefetch(self, *fields: str) -> "QuerySet[TModel]": ...

    def iterator(self, *, page_size: int | None = None) -> "Paginator[TModel]":
        return Paginator(self, page_size=page_size or self.PAGE_SIZE)

    async def exists(self) -> bool:
        """Check if any results exist"""
        return await self.count() > 0

    async def count(self) -> int:
        """Get count of results (uses $count)"""
        if self._count_cache is not None:
            return self._count_cache

        qs = self.with_count().top(1)
        params = qs._build_params()

        assert qs._endpoint is not None
        response = await self._client.get(
            self._endpoint, params=params, headers=qs._headers
        )
        count = response.get("@odata.count", len(response.get("value", [])))
        self._count_cache = count
        return count

    async def get(self, id: str | None = None, **kwargs) -> TModel:
        if id:
            response = await self._client.get(f"{self._endpoint}/{id}")
            return self._model_class(
                graph_data=response,  # pyright: ignore[reportCallIssue]
                client=self._client,  # pyright: ignore[reportCallIssue]
                endpoint=self._endpoint,  # pyright: ignore[reportCallIssue]
            )

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

    async def first(self) -> TModel | None:
        qs = self.top(1)
        params = qs._build_params()

        assert self._endpoint is not None
        response = await self._client.get(
            self._endpoint, params=params, headers=self._headers
        )
        if response:
            return self._model_class(
                graph_data=response,  # pyright: ignore[reportCallIssue]
                client=self._client,  # pyright: ignore[reportCallIssue]
                endpoint=self._endpoint,  # pyright: ignore[reportCallIssue]
            )
        return None

    def __aiter__(self) -> AsyncIterator[TModel]:
        """Execute the query and fetch results"""
        if not self._all:
            return self.iterator()._fetch_page(1)
        return self.iterator().all()

    def _build_params(self) -> dict[str, Any]:
        """Build OData query parameters"""
        compiled_params = {}
        params = self._params

        if values := params.get("$filter"):
            compiled_params["$filter"] = " and ".join(f"({v})" for v in values)

        if values := params.get("$select"):
            compiled_params["$select"] = ",".join([to_camel_case(v) for v in values])

        if values := params.get("$orderby"):
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

        if values := params.get("$search"):
            compiled_params["$search"] = " AND ".join(values)

        if value := params.get("$top"):
            compiled_params["$top"] = str(value)

        if expands := params.get("$expand"):
            parts: list[str] = []
            for name, fields in expands.items():
                if fields:
                    parts.append(f"{name}($select={','.join(sorted(fields))})")
                else:
                    parts.append(name)
            compiled_params["$expand"] = ",".join(parts)

        return compiled_params


class Paginator(Generic[TModel]):
    def __init__(
        self,
        queryset: QuerySet[TModel],
        *,
        page_size: int | None = None,
    ) -> None:
        self._qs = queryset._clone()
        self._model_class = queryset._model_class
        self._client = queryset._client
        self._endpoint = queryset._endpoint
        self._cache_objects = queryset._cache_objects
        self._page_size = page_size or 50
        self._current_page_number: int = 1
        self._next_link: str | None = None

    async def next_page(self) -> AsyncIterator[TModel]:
        next_page = self._current_page_number + 1
        objects = self._fetch_page(next_page)

        try:
            first = await anext(objects)
        except StopAsyncIteration:
            return

        self._current_page_number = next_page
        yield first
        async for obj in objects:
            yield obj

    async def total_count(self) -> int | None:
        if (_cache := self._qs._count_cache) is None:
            return await self._qs.count()
        return _cache

    async def total_pages(self) -> int | None: ...

    async def has_next(self) -> bool:
        if not self._cache_objects.get(1):
            async for _ in self._fetch_page(1):
                ...
        return bool(self._next_link)

    def __aiter__(self) -> AsyncIterator[TModel]:
        return self._fetch_page(self._current_page_number)

    async def all(self) -> AsyncIterator[TModel]:
        page_numbers = sorted(self._cache_objects)

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

    def first_page(self) -> AsyncIterator[TModel]:
        return self._fetch_page(1)

    async def _fetch_page(
        self, page_number: int | None = None
    ) -> AsyncIterator[TModel]:
        """Fetch a single page of results"""

        if page_number is None:
            page_number = self._current_page_number

        # e.g. page_number = 3, current_page_number = 1
        if page_number > self._current_page_number + 1:
            # $skip and $top not supported at this stage
            raise ValueError(f"Unable to fetch page, {page_number}.")

        if page_number < 1:
            raise ValueError("page_number must be greater than 0.")

        # return cached page immediately without enforcing gap rules
        objects = self._cache_objects.get(page_number)
        if objects:
            for obj in objects:
                yield obj
            return

        if page_number == 1:
            assert self._endpoint is not None
            params = self._qs._build_params()
            if params.get("$top") is None:
                params["$top"] = str(self._page_size)
            response = await self._client.get(
                self._endpoint, params=params, headers=self._qs._headers
            )
        else:
            if not self._next_link:
                return
            response = await self._client.get(
                url=self._next_link, headers=self._qs._headers
            )

        self._next_link = response.get("@odata.nextLink")
        objects = self._cache_objects.setdefault(page_number, [])

        for item in response.get("value", []):
            obj = self._model_class(
                graph_data=item,  # pyright: ignore[reportCallIssue]
                client=self._client,  # pyright: ignore[reportCallIssue]
                endpoint=self._endpoint,  # pyright: ignore[reportCallIssue]
            )
            objects.append(obj)
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


class DoesNotExist(Exception): ...


class MultipleObjectsReturned(Exception): ...
