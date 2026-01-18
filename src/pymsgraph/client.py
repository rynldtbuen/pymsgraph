from __future__ import annotations

import platform
import sys
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Generic, TypeVar, overload

import httpx

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore

from pymsgraph.models import (
    GroupQuerySet,
    SiteQuerySet,
    SubscribedSkuQuerySet,
    UserQuerySet,
)

if TYPE_CHECKING:
    from pymsgraph.auth import TokenProvider
    from pymsgraph.models.query import QuerySet


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


_Tqs = TypeVar("_Tqs", bound="QuerySet")


class RootQuerySetDescriptor(Generic[_Tqs]):
    def __init__(self, queryset_class: type[_Tqs]) -> None:
        self.queryset_class = queryset_class

    @overload
    def __get__(
        self, obj: None, owner: type["Client"] | None = None
    ) -> "RootQuerySetDescriptor[_Tqs]": ...

    @overload
    def __get__(self, obj: "Client", owner: type["Client"] | None = None) -> _Tqs: ...

    def __get__(
        self, obj: "Client | None", owner: type["Client"] | None = None
    ) -> "_Tqs | RootQuerySetDescriptor[_Tqs]":
        if obj is None:
            return self

        return self.queryset_class(obj)


class Client:

    def __init__(
        self,
        token_provider: "TokenProvider",
        *,
        base_url: str = "https://graph.microsoft.com/v1.0",
        scopes: Sequence[str] | None = None,
        default_headers: Mapping[str, str] | None = None,
        timeout: float | None = 30.0,
        http: httpx.AsyncClient | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.token_provider = token_provider
        self.base_url = base_url.rstrip("/")
        self.scopes = list(scopes) if scopes else None

        self._owns_http = http is None
        self.http = http or httpx.AsyncClient(timeout=timeout)

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

    async def get(
        self,
        path: str | None = None,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        if path:
            url = self._url(path)
        if url is None:
            raise ValueError("Argument required, path/url.")
        resp = await self.http.get(url, params=params, headers=self._headers(headers))
        self._raise_for_status(resp)
        data = self._json_or_none(resp)
        return data or {}

    async def post(
        self,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        resp = await self.http.post(
            self._url(path),
            params=params,
            json=dict(body) if body is not None else None,
            headers=self._headers(headers),
        )
        self._raise_for_status(resp)
        data = self._json_or_none(resp)
        return data or {}

    async def put(
        self,
        path: str,
        *,
        content: bytes | str | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        content = content.encode() if isinstance(content, str) else content
        resp = await self.http.put(
            self._url(path),
            params=params,
            content=content,
            headers=self._headers(headers),
        )
        self._raise_for_status(resp)
        data = self._json_or_none(resp)
        return data or {}

    async def get_content(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        resp = await self.http.get(
            self._url(path),
            params=params,
            headers=self._headers(headers),
        )
        self._raise_for_status(resp)
        return resp.content

    async def patch(
        self,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        resp = await self.http.patch(
            self._url(path),
            params=params,
            json=dict(body) if body is not None else None,
            headers=self._headers(headers),
        )
        self._raise_for_status(resp)
        return self._json_or_none(resp)

    async def delete(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        resp = await self.http.delete(
            self._url(path), params=params, headers=self._headers(headers)
        )
        self._raise_for_status(resp)
        return self._json_or_none(resp)

    async def close(self) -> None:
        if self._owns_http:
            await self.http.aclose()

    async def __aenter__(self) -> "Client":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self, headers: Mapping[str, str] | None = None) -> dict[str, str]:
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
                f"Graph API error {resp.status_code}: {detail}: {resp.url}",
                request=e.request,
                response=e.response,
            ) from None

    def _json_or_none(self, resp: httpx.Response) -> Any:
        if resp.status_code == 204:
            return None
        if not resp.content:
            return None
        return resp.json()

    groups = RootQuerySetDescriptor(GroupQuerySet)
    subscribed_skus = RootQuerySetDescriptor(SubscribedSkuQuerySet)
    sites = RootQuerySetDescriptor(SiteQuerySet)
    users = RootQuerySetDescriptor(UserQuerySet)
