from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import msal


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

    Encrypted persisted token cache is used only when `token_cache_path`
    is provided; otherwise MSAL uses in-memory cache.
    """

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        authority: str | None = None,
        token_cache_path: str | Path | None = None,
        allow_interactive: bool = True,
        login_hint: str | None = None,
        default_scopes: Sequence[str] | None = None,
    ) -> None:
        self.authority = authority or f"https://login.microsoftonline.com/{tenant_id}"
        self.allow_interactive = allow_interactive
        self.login_hint = login_hint

        token_cache: Any | None = None
        if token_cache_path is not None:
            token_cache = self._build_encrypted_persisted_cache(token_cache_path)

        self.app = msal.PublicClientApplication(
            client_id=client_id,
            authority=self.authority,
            token_cache=token_cache,
        )
        self._default_scopes: list[str] | None = (
            list(default_scopes) if default_scopes else None
        )
        self._token_cache_path = token_cache_path

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

    @staticmethod
    def _build_encrypted_persisted_cache(cache_path: str | Path | None = None) -> Any:
        """Create an encrypted persisted cache for delegated auth tokens."""
        try:
            import msal_extensions  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise RuntimeError(
                "PublicClientAuth requires 'msal-extensions' for encrypted persisted "
                "token cache. Install it with: pip install msal-extensions"
            ) from exc

        if cache_path is None:
            cache_file = Path.home() / ".pymsgraph" / "msal_token_cache.bin"
        else:
            cache_file = Path(cache_path).expanduser()
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            persistence = msal_extensions.build_encrypted_persistence(str(cache_file))
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize encrypted token cache at '{cache_file}': {exc}"
            ) from exc

        if persistence is None:
            raise RuntimeError(
                "Encrypted token cache is unavailable on this platform/runtime. "
                "Provide an explicit cache=... or configure a supported secret store."
            )
        return msal_extensions.PersistedTokenCache(persistence)
