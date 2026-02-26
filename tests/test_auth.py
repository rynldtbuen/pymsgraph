from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import pymsgraph.auth as auth


def test_public_client_auth_uses_encrypted_persisted_cache_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}
    fake_persistence = object()

    class FakePersistedTokenCache:
        def __init__(self, persistence: object) -> None:
            self.persistence = persistence

    def fake_build_encrypted_persistence(path: str) -> object:
        captured["cache_path"] = path
        return fake_persistence

    fake_extensions = SimpleNamespace(
        build_encrypted_persistence=fake_build_encrypted_persistence,
        PersistedTokenCache=FakePersistedTokenCache,
    )
    monkeypatch.setattr(auth, "_import_msal_extensions", lambda: fake_extensions)

    class FakePublicClientApplication:
        def __init__(
            self, *, client_id: str, authority: str, token_cache: object | None = None
        ) -> None:
            captured["client_id"] = client_id
            captured["authority"] = authority
            captured["token_cache"] = token_cache

    monkeypatch.setattr(
        auth.msal, "PublicClientApplication", FakePublicClientApplication
    )

    cache_path = tmp_path / "token_cache.bin"
    provider = auth.PublicClientAuth(
        tenant_id="tenant-id",
        client_id="client-id",
        token_cache_path=cache_path,
        allow_interactive=False,
        default_scopes=["User.Read"],
    )

    assert provider.authority.endswith("/tenant-id")
    assert captured["cache_path"] == str(cache_path)
    assert isinstance(captured["token_cache"], FakePersistedTokenCache)
    assert captured["token_cache"].persistence is fake_persistence


def test_public_client_auth_uses_in_memory_cache_when_path_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        auth,
        "_import_msal_extensions",
        lambda: (_ for _ in ()).throw(AssertionError("Should not import extensions")),
    )

    class FakePublicClientApplication:
        def __init__(
            self, *, client_id: str, authority: str, token_cache: object | None = None
        ) -> None:
            captured["token_cache"] = token_cache

    monkeypatch.setattr(
        auth.msal, "PublicClientApplication", FakePublicClientApplication
    )

    provider = auth.PublicClientAuth(
        tenant_id="tenant-id",
        client_id="client-id",
        allow_interactive=False,
        default_scopes=["User.Read"],
    )

    assert provider.authority.endswith("/tenant-id")
    assert captured["token_cache"] is None


# def test_public_client_auth_raises_when_extensions_missing(
#     monkeypatch: pytest.MonkeyPatch, tmp_path: Path
# ) -> None:
#     monkeypatch.setattr(
#         auth, "_import_msal_extensions", lambda: (_ for _ in ()).throw(ImportError())
#     )

#     with pytest.raises(RuntimeError, match="msal-extensions"):
#         auth.PublicClientAuth(
#             tenant_id="tenant-id",
#             client_id="client-id",
#             token_cache_path=tmp_path / "token_cache.bin",
#             allow_interactive=False,
#             default_scopes=["User.Read"],
#         )


def test_public_client_auth_raises_when_encrypted_persistence_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_extensions = SimpleNamespace(
        build_encrypted_persistence=lambda path: None,
        PersistedTokenCache=lambda persistence: object(),
    )
    monkeypatch.setattr(auth, "_import_msal_extensions", lambda: fake_extensions)

    with pytest.raises(RuntimeError, match="Encrypted token cache is unavailable"):
        auth.PublicClientAuth(
            tenant_id="tenant-id",
            client_id="client-id",
            token_cache_path=tmp_path / "token_cache.bin",
            allow_interactive=False,
            default_scopes=["User.Read"],
        )
