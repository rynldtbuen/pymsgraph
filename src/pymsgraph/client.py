from __future__ import annotations

import platform
import sys
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import httpx

from pymsgraph.models import query

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore

if TYPE_CHECKING:
    from .auth import TokenProvider

__all__ = ["Client"]


def _default_user_agent() -> str:
    """Build a descriptive UA: pymsgraph/<version> (python X.Y; os)."""
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    os_name = (platform.system() or "unknown").lower()
    try:
        version = importlib_metadata.version("pymsgraph")
    except importlib_metadata.PackageNotFoundError:
        version = "0.0.0"
    return f"pymsgraph/{version} (python {py_ver}; {os_name})"


# TQS = TypeVar("TQS", bound=QuerySet)


# class ResourceDescriptor(Generic[TQS]):
#     """
#     Simple descriptor that binds a QuerySet to a Client instance.
#     """

#     def __init__(
#         self,
#         queryset: str | type[QuerySet] | None = None,
#         model: type[TModel] | str | None = None,
#         # *,
#         # endpoint: str | None = None,
#     ):

#         self.queryset_path = queryset_path
#         self.model = model
#         # self.endpoint = endpoint
#         # self.model = model
#         # self._cache: dict[int, Any] = {}

#     def __get__(
#         self, obj: "Client", objtype: type["Client"] | None = None
#     ) -> QuerySet | ResourceDescriptor:
#         if obj is None:
#             return self

#         cache = getattr(obj, "_qs_cache", None)
#         if cache is None:
#             cache = obj._qs_cache = {}  # type: ignore
#         key = self.queryset_path
#         if key in cache:
#             return cache[key]

#         if self.queryset_path is not None:
#             queryset_class: type[QuerySet] = utils.get_queryset_class(
#                 self.queryset_path
#             )
#         else:
#             queryset_class = QuerySet

#         model = self.model or getattr(queryset_class, "model", None)
#         if model is None:
#             raise ValueError(
#                 "Model must be pass when intializing a ResourceDescriptor or defining when subclassing a QuerySet"
#             )

#         qs = queryset_class(client=obj, model=model)
#         cache[key] = qs
#         return qs


class Client:

    # groups = QuerySetDescriptor("group.GroupQuerySet")
    # users = QuerySetDescriptor("group.UserQuerySet")
    # subscribed_skus = QuerySetDescriptor("subscribed_sku.SubscribedSkuQuerySet")

    def __init__(
        self,
        token_provider: "TokenProvider",
        *,
        base_url: str = "https://graph.microsoft.com/v1.0",
        scopes: Sequence[str] | None = None,
        default_headers: Mapping[str, str] | None = None,
        timeout: float | None = 30.0,
        http: httpx.Client | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.token_provider = token_provider
        self.base_url = base_url.rstrip("/")
        self.scopes = list(scopes) if scopes else None

        self._owns_http = http is None
        self.http = http or httpx.Client(timeout=timeout)

        ua = _default_user_agent()
        if user_agent:
            ua = f"{user_agent} {ua}"

        self.default_headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": ua,
        }
        if default_headers:
            self.default_headers.update(dict(default_headers))

    # ---- internals ----
    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self, headers: Mapping[str, str] | None) -> dict[str, str]:
        token = self.token_provider.get_access_token(self.scopes)
        out = dict(self.default_headers)
        out["Authorization"] = f"Bearer {token}"
        if headers:
            out.update(dict(headers))
        return out

    def _raise_for_status(self, resp: httpx.Response) -> None:
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Try to enrich error with Graph JSON body if present
            detail: Any
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise httpx.HTTPStatusError(
                f"Graph API error {resp.status_code}: {detail}",
                request=e.request,
                response=e.response,
            ) from None

    def _json_or_none(self, resp: httpx.Response) -> Any:
        if resp.status_code == 204:
            return None
        if not resp.content:
            return None
        return resp.json()

    # ---- public API used by models/queryset ----
    def get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        resp = self.http.get(
            self._url(path), params=params, headers=self._headers(headers)
        )
        self._raise_for_status(resp)
        data = self._json_or_none(resp)
        return data or {}

    def post(
        self,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        resp = self.http.post(
            self._url(path),
            params=params,
            json=dict(json_body) if json_body is not None else None,
            headers=self._headers(headers),
        )
        self._raise_for_status(resp)
        data = self._json_or_none(resp)
        return data or {}

    def put(
        self,
        path: str,
        *,
        content: bytes | str | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        body = content.encode() if isinstance(content, str) else content
        resp = self.http.put(
            self._url(path),
            params=params,
            content=body,
            headers=self._headers(headers),
        )
        self._raise_for_status(resp)
        data = self._json_or_none(resp)
        return data or {}

    def get_content(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        resp = self.http.get(
            self._url(path),
            params=params,
            headers=self._headers(headers),
        )
        self._raise_for_status(resp)
        return resp.content

    def patch(
        self,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        resp = self.http.patch(
            self._url(path),
            params=params,
            json=dict(json_body) if json_body is not None else None,
            headers=self._headers(headers),
        )
        self._raise_for_status(resp)
        return self._json_or_none(resp)

    def delete(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        resp = self.http.delete(
            self._url(path), params=params, headers=self._headers(headers)
        )
        self._raise_for_status(resp)
        return self._json_or_none(resp)

    # ---- lifecycle ----
    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def groups(self) -> query.GroupQuerySet:
        return query.GroupQuerySet(self)

    @property
    def users(self) -> query.UserQuerySet:
        return query.UserQuerySet(self)

    @property
    def subscribed_skus(self) -> query.SubscribedSkuQuerySet:
        return query.SubscribedSkuQuerySet(self)

    @property
    def drives(self) -> query.DriveQuerySet:
        return query.DriveQuerySet(self)

    @property
    def sites(self) -> query.SiteQuerySet:
        return query.SiteQuerySet(self)
