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


class Client:

    def __init__(
        self,
        token_provider: TokenProvider,
        *,
        http: httpx.Client | None = None,
        base_url: str = "https://graph.microsoft.com/v1.0",
        scopes: Sequence[str] | None = None,
        default_headers: Mapping[str, str] | None = None,
        timeout: float | None = 30.0,
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

    def configure_default(self) -> "Client":
        # make this client the default for all models
        from pymsgraph.models.base import GraphModel

        GraphModel.configure_default(self)
        return self
