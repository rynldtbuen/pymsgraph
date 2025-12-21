from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TYPE_CHECKING
import platform
import sys

import httpx

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore

if TYPE_CHECKING:
    from .auth import TokenProvider
    from pymsgraph.query import TModel

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


class ResourceDescriptor:
    """
    Simple descriptor that binds a QuerySet to a Client instance.
    """

    def __init__(
        self,
        qs_path: str | None = None,
        *,
        endpoint: str | None = None,
        model: type[TModel] | None = None,
    ):
        self.qs_path = qs_path
        self.endpoint = endpoint
        self.model = model
        self._cache: dict[int, Any] = {}

    def __get__(self, obj: "Client", objtype=None):
        if obj is None:
            return self

        cache = getattr(obj, "_qs_cache", None)
        if cache is None:
            cache = obj._qs_cache = {}  # type: ignore
        key = (self.qs_path, self.endpoint, self.model)
        if key in cache:
            return cache[key]

        if self.qs_path is not None:
            import importlib

            module_name, _, cls_name = self.qs_path.rpartition(".")
            if not module_name or not cls_name:
                raise ImportError(f"Invalid qs_path, '{self.qs_path}'")

            mod = importlib.import_module(f"pymsgraph.models.{module_name}")
            qs_cls = getattr(mod, cls_name)
        else:
            from pymsgraph.query import QuerySet

            qs_cls = QuerySet

        e = self.endpoint or getattr(qs_cls, "endpoint", None)
        if e is None:
            raise ValueError(
                "Endpoint must be specified in descriptor or QuerySet class"
            )
        m = self.model or getattr(qs_cls, "model", None)
        if m is None:
            raise ValueError("Model must be specified in descriptor or QuerySet class")

        qs = qs_cls(client=obj, model=m, endpoint=e)
        cache[key] = qs
        return qs


class Client:

    users = ResourceDescriptor("user.UserQuerySet")

    def __init__(
        self,
        token_provider: TokenProvider,
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
