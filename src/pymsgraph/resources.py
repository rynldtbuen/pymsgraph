from abc import ABC, abstractmethod
from ast import Mult
from json import JSONDecodeError
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Iterator,
    Self,
    TypeVar,
    Union,
    cast,
)

if TYPE_CHECKING:
    from pymsgraph import Client

import requests

R = TypeVar("R", bound="Resource")
MVR = TypeVar("MVR", bound="MultiValuedResource")


# class RequestMethod:
#     GET = False
#     POST = False
#     PATCH = False
#     DELETE = False
#     PUT = False


# class RequestQueryParam:
#     SELECT = False
#     EXPAND = False
#     FILTER = False
#     ORDERBY = False
#     TOP = False
#     COUNT = False
#     SEARCH = False


class Resource(ABC):
    URL = "https://graph.microsoft.com/v1.0"
    MODELS = {}

    class RequestMethod:
        GET = False
        POST = False
        PATCH = False
        DELETE = False
        PUT = False

    class RequestQueryParam:
        SELECT = False
        EXPAND = False
        FILTER = False
        ORDERBY = False
        TOP = False
        COUNT = False
        SEARCH = False

    def __init_subclass__(cls: type[R]) -> None:
        super().__init_subclass__()
        cls.MODELS[cls.__name__] = cls

    def __init__(
        self,
        client: "Client",
        data: dict[str, Any] | None = None,
        parent: "Resource | None" = None,
        **kwargs,
    ) -> None:

        has_changed: bool = True
        if data is None:
            data = {}

        self._client = client
        self._data = data
        self._parent = parent
        self._has_changed = has_changed
        self._query_params: dict[str, Any] = {}
        # self._response: requests.Response

        self._set_kwargs(kwargs)

    @property
    @abstractmethod
    def relative_url(self) -> str:
        pass

    @property
    def url(self) -> str:
        parent = self._parent
        if parent is None:
            return f"{self.URL}{self.relative_url}"
        return f"{parent.url}{self.relative_url}"

    @property
    def url_with_query_params(self) -> str:
        query_params = self.query_params
        if query_params:
            return f"{self.url}?{'&'.join(query_params)}"
        return self.url

    @property
    def query_params(self) -> list[str]:
        return [f"${k}={v}" for k, v in self._query_params.items()]

    def get(self: R) -> R:
        if not self.RequestMethod.GET:
            raise ValueError(f"Endpoint does not support GET method, '{self.url}'")
        if self._has_changed:

            response = requests.get(
                self.url_with_query_params, headers=self._client._headers
            )
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                # print(response.json())
                raise
            try:
                self._data = response.json()
            except JSONDecodeError:
                self._get_response = response
            self._has_changed = False
        return self

    def patch(self: R, data: dict[str, Any]) -> R:
        if not self.RequestMethod.PATCH:
            raise ValueError(f"Endpoint does not support PATCH method, '{self.url}'")
        response = requests.patch(self.url, headers=self._client._headers, json=data)
        self._patch_response = response
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            print(response.json())
            raise
        self._has_changed = True
        return self

    def post(self: R, payload: dict[str, Any] | None = None) -> R:
        if not self.RequestMethod.POST:
            raise ValueError(f"Endpoint does not support POST method, '{self.url}'")
        if payload is None:
            payload = {}
        response = requests.post(self.url, headers=self._client._headers, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            print(response.json())
            raise
        self._has_changed = True
        return self

    def delete(self: R) -> R:
        if not self.RequestMethod.DELETE:
            raise ValueError(f"Endpoint does not support DELETE method, '{self.url}'")
        response = requests.delete(self.url, headers=self._client._headers)
        self._delete_response = response
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            print(response.json())
            raise
        self._has_changed = True
        return self

    def put(self: R, data: str | bytes | dict[str, Any]) -> R:
        if not self.RequestMethod.PUT:
            raise ValueError(f"Endpoint does not support PUT method, '{self.url}'")
        response = requests.put(self.url, data=data, headers=self._client._headers)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            print(response.text)
            raise

        self._put_response = response
        self._has_changed = True
        return self

    def select(self: R, value: str) -> R:
        self._add_query_params("SELECT", value.strip())
        return self

    def expand(self: R, value: str) -> R:
        self._add_query_params("EXPAND", value.strip())
        return self

    def asdict(self) -> dict[str, Any]:
        return self._data

    def get_from_raw_relative_url(self, relative_url):
        return requests.get(f"{self.URL}/{relative_url}", headers=self._client._headers)

    def _add_query_params(self, key: str, value: str) -> None:
        if not getattr(self.RequestQueryParam, key, False):
            raise ValueError(f"Query parameter is not supported, '{key}'.")
        self._query_params[key.lower()] = value.strip()
        self._has_changed = True

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        pass

    @classmethod
    def as_descriptor(cls: type[R]) -> "ResourceProperty[R]":
        return ResourceProperty(cls)


class SingleValuedResource(Resource):
    Content: type["SingleValuedResource"]

    class RequestMethod(Resource.RequestMethod):
        GET = True

    class RequestQueryParam(Resource.RequestQueryParam):
        SELECT = True


class MultiValuedResource(SingleValuedResource, Generic[R]):
    class RequestQueryParam(SingleValuedResource.RequestQueryParam):
        FILTER = True
        ORDERBY = True

    ITEM_CLASS: str

    def __init_subclass__(cls: type[Self], **kwargs: dict[str, Any]) -> None:
        if cls.ITEM_CLASS is None:
            raise AttributeError(
                "Attribute 'ITEM_CLASS' is required if subclassing 'MultiValuedResource. e.g. Users item class is User.'"
            )
        super().__init_subclass__()

    def __init__(self, client: "Client", *args, **kwargs):
        super().__init__(client, *args, **kwargs)
        self._mdata: dict[int, dict[str, Any]] = {0: self._data}
        self._current_page: int = 0
        self._objects: dict[int, tuple[R, ...]] = {}

    @property
    def current_page(self) -> int:
        return self._current_page + 1

    @property
    def current_items(self) -> tuple[R, ...]:
        current_page = self._current_page

        try:
            return self._objects[current_page]
        except KeyError:
            return tuple(self._iter_objects(current_page))

    def asdict(self) -> dict[str, Any]:
        return self._mdata[self.current_page]["value"]

    def count_fetched_items(self) -> int:
        return sum([len(item["value"]) for item in self._mdata.values()])

    def has_next_items(self) -> bool:
        return bool(self._mdata.get(self._current_page, {}).get("@odata.nextLink"))

    def get_next_items(self: MVR) -> MVR:
        current_page = self._current_page
        next_page = current_page + 1
        try:
            data = self._mdata[next_page]
        except KeyError:
            next_link = self._mdata[current_page].get("@odata.nextLink")
            if next_link:
                response = requests.get(next_link, headers=self._client._headers)

                try:
                    response.raise_for_status()
                except requests.HTTPError:
                    raise

                data = response.json()
                self._mdata[next_page] = data
            else:
                raise ValueError("No more items")

        self._current_page = next_page
        return self

    def iter_fetched_items(self) -> Iterator[R]:
        objects = self._objects

        for page in self._mdata:
            try:
                _iter_objects = iter(objects[page])
            except KeyError:
                yield from self._iter_objects(page)
            else:
                for obj in _iter_objects:
                    yield obj

    def iter_all_items(self) -> Iterator[R]:
        while self.has_next_items():
            self.get_next_items()
        else:
            yield from self.iter_fetched_items()

    def get(self: MVR) -> MVR:
        if not self.RequestMethod.GET:
            raise ValueError(f"Endpoint does not support GET method, '{self.url}'")
        if self._has_changed:
            headers = self._get_headers()
            response = requests.get(self.url_with_query_params, headers=headers)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                print(response.json())
                raise
            self._mdata.clear()
            self._objects.clear()
            self._has_changed = False
            self._mdata[0] = response.json()
        return self

    def filter(self: MVR, value: str) -> MVR:
        self._add_query_params("FILTER", value.strip())
        return self

    def filter__and(self: MVR, value: str) -> MVR:
        try:
            self._query_params["filter"] += f" and {value}"
        except KeyError:
            raise ValueError(
                f"Paremater does not exist. Can't append filter value, '{value}'"
            )
        return self

    def filter__or(self: MVR, value: str) -> MVR:
        try:
            self._query_params["filter"] += f" or {value}"
        except KeyError:
            raise ValueError(
                f"Paremater does not exist. Can't append filter value, '{value}'"
            )
        return self

    def orderby(self: MVR, value: str) -> MVR:
        self._add_query_params("ORDERBY", value.strip())
        return self

    def top(self: MVR, value: str | int) -> MVR:
        self._add_query_params("TOP", str(value).strip())
        return self

    def count(self: MVR) -> MVR:
        self._add_query_params("COUNT", "true")
        return self

    def search(self: MVR, value: str) -> MVR:
        result = []
        operators = {"AND", "OR"}

        for item in value.split():
            _item = item.strip()
            if _item in operators:
                result.append(_item)
            else:
                result.append(f'"{_item}"')

        self._add_query_params("SEARCH", " ".join(result))
        return self

    def _iter_objects(self, page: int) -> Iterator[R]:
        klass: type[R] = self.MODELS[self.ITEM_CLASS]
        client = self._client

        page_objects = []
        page_objects_apppend = page_objects.append

        for item in self._mdata[page]["value"]:
            # obj = klass(client, data=item, parent=self)
            obj = self._get_obj(klass, client, item)
            page_objects_apppend(obj)
            yield obj

        self._objects[page] = tuple(page_objects)

    def _get_obj(self, klass: type[R], client: "Client", data: dict[str, Any]) -> R:
        return klass(client, data=data, parent=self)

    def _get_headers(self):
        headers = self._client._headers
        if "count" in self._query_params:
            headers["ConsistencyLevel"] = "eventual"
        return headers


class ResourceProperty(Generic[R]):
    def __init__(self, klass: type[R]) -> None:
        self.resource_class = klass

    def __set_name__(self, owner, name) -> None:
        self.name = "".join(map(lambda x: x.title(), name.split("_")))

    def __get__(self, obj: "Client", objtype: type["Client"] | None = None) -> R:
        return self.resource_class(obj)

    def __set__(self, obj: "Client", value: Any) -> None:
        raise AttributeError(f"Attribute '{self.name}' is read-only.")

    def __delete__(self, obj: "Client") -> None:
        raise AttributeError(f"Attribute '{self.name}' is read-only.")
