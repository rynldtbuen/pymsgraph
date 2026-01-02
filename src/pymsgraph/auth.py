from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

import msal


__all__ = [
    "ConfidentialClientAuth",
    "PublicClientAuth",
]


class TokenProvider(Protocol):
    """Minimal interface GraphClient needs.

    Your MSAL provider can implement this.
    """

    def get_access_token(
        self, scopes: Sequence[str] | None = None, *, force_refresh: bool = False
    ) -> str: ...


class ConfidentialClientAuth(TokenProvider):
    """Client-credentials token provider (app-only) using MSAL.

    Example:
        provider = ConfidentialClientAuth(
            tenant_id="...",
            client_id="...",
            client_secret="...",
        )
        graph = GraphClient(provider, scopes=["https://graph.microsoft.com/.default"])

    MSAL will cache tokens in-memory by default. Pass a SerializableTokenCache
    if you want to persist it.
    """

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str | None = None,
        client_certificate: dict[str, Any] | None = None,
        authority: str | None = None,
        cache: Any | None = None,
    ) -> None:
        if not client_secret and not client_certificate:
            raise ValueError("Provide either client_secret or client_certificate.")

        self._default_scopes: list[str] = ["https://graph.microsoft.com/.default"]
        self.authority = authority or f"https://login.microsoftonline.com/{tenant_id}"

        self.app = msal.ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret or client_certificate,
            authority=self.authority,
            token_cache=cache,
        )

    def get_access_token(
        self, scopes: Sequence[str] | None = None, *, force_refresh: bool = False
    ) -> str:
        scopes_list = list(scopes) if scopes else self._default_scopes

        # silent cache lookup first
        result: dict[str, Any] | None = self.app.acquire_token_silent(
            scopes_list, account=None, force_refresh=force_refresh
        )
        if not result:
            result = self.app.acquire_token_for_client(scopes=scopes_list)

        token = (result or {}).get("access_token")
        if not token:
            err = (result or {}).get("error")
            desc = (result or {}).get("error_description")
            corr = (result or {}).get("correlation_id")
            raise RuntimeError(
                f"MSAL failed to acquire token "
                f"(error={err!r}, description={desc!r}, correlation_id={corr!r})"
            )
        return token


class PublicClientAuth(TokenProvider):
    """Delegated token provider (interactive fallback) using MSAL.

    This is suitable for CLIs / desktop tooling.

    If `allow_interactive=False`, the provider will only use the cache and will
    raise if it cannot acquire a token silently.

    Note: Delegated auth requires explicit scopes like ["User.Read"].
    """

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        authority: str | None = None,
        cache: Any | None = None,
        allow_interactive: bool = True,
        login_hint: str | None = None,
        default_scopes: Sequence[str] | None = None,
    ) -> None:
        self.authority = authority or f"https://login.microsoftonline.com/{tenant_id}"
        self.allow_interactive = allow_interactive
        self.login_hint = login_hint

        self.app = msal.PublicClientApplication(
            client_id=client_id,
            authority=self.authority,
            token_cache=cache,
        )
        self._default_scopes: list[str] | None = (
            list(default_scopes) if default_scopes else None
        )

    def get_access_token(
        self, scopes: Sequence[str] | None = None, *, force_refresh: bool = False
    ) -> str:
        scopes_list = list(scopes) if scopes else (self._default_scopes or [])
        if not scopes_list:
            raise ValueError(
                "Delegated auth requires explicit scopes. "
                "Pass scopes=... or set default_scopes on the provider."
            )

        accounts = self.app.get_accounts()
        account = accounts[0] if accounts else None

        result: dict[str, Any] | None = self.app.acquire_token_silent(
            scopes_list, account=account, force_refresh=force_refresh
        )
        if not result and self.allow_interactive:
            # Browser-based auth (works well for CLIs)
            result = self.app.acquire_token_interactive(
                scopes=scopes_list,
                login_hint=self.login_hint,
            )

        token = (result or {}).get("access_token")
        if not token:
            err = (result or {}).get("error")
            desc = (result or {}).get("error_description")
            corr = (result or {}).get("correlation_id")
            raise RuntimeError(
                f"MSAL failed to acquire token "
                f"(error={err!r}, description={desc!r}, correlation_id={corr!r})"
            )
        return token
