from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable
import importlib
import re
import secrets
import string
import time
from typing import TYPE_CHECKING, Any, Iterator, TypeVar
import uuid


if TYPE_CHECKING:
    from pymsgraph.models.base import Model

T = TypeVar("T")


def generate_password(length: int = 12) -> str:
    """
    Generate a strong random password.

    Guarantees:
    - length >= 12 (enforced)
    - at least 1 lowercase, 1 uppercase, 1 digit, 1 symbol

    Uses `secrets` for cryptographic randomness.
    """
    if length < 12:
        raise ValueError("length must be at least 12")

    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    # Avoid quotes/backslash which can be annoying in some contexts
    symbols = "!@#$%^&*()-_=+?"

    # Ensure required categories
    required = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]

    all_chars = lowercase + uppercase + digits + symbols

    # Fill the rest
    remaining = [secrets.choice(all_chars) for _ in range(length - len(required))]

    # Shuffle so required chars aren't predictable positions
    chars = required + remaining
    secrets.SystemRandom().shuffle(chars)

    return "".join(chars)


_CAMEL_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_2 = re.compile(r"([a-z0-9])([A-Z])")


def to_snake_case(s: str) -> str:
    """
    Convert camelCase / PascalCase to snake_case.

    Examples:
        "displayName" -> "display_name"
        "UserPrincipalName" -> "user_principal_name"
        "SKUId" -> "sku_id"
        "servicePlanId2" -> "service_plan_id2"
    """
    s = s.strip()
    if not s:
        return s

    s = s.replace("-", "_").replace(" ", "_")
    s = _CAMEL_1.sub(r"\1_\2", s)
    s = _CAMEL_2.sub(r"\1_\2", s)
    return s.lower()


def to_camel_case(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def get_model_class(model_name: str) -> type["Model"]:
    module_name = to_snake_case(model_name)
    mod = importlib.import_module(f"pymsgraph.models.{module_name}")
    return getattr(mod, model_name)


class SimpleCache:
    def __init__(
        self,
        *,
        loader: Callable[[], Any] | None = None,
        ttl: int | float = 600,
    ) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._loader = loader
        self._loaded = False
        self._ttl = ttl

    async def get(self, key: str) -> Any | None:
        async def _load():
            if not self._loaded and (loader := self._loader):
                data = await loader()
                expires_at = time.time() + self._ttl
                if isinstance(data, dict):
                    for k, v in data.items():
                        self._store[str(k)] = (expires_at, v)
                else:
                    self._store[key] = (expires_at, data)
                self._loaded = True

        def _get():
            item = self._store.get(key)
            if item is None:
                return (0, None)
            return item

        await _load()

        expires_at, value = _get()

        if time.time() > expires_at:
            if self._loader is None:
                self._store.pop(key, None)
                return None

            self._store.clear()
            await _load()
            _, value = _get()

        return value

    def set(self, key: str, value: Any, *, ttl: int | float | None = None) -> None:
        if self._loader:
            raise RuntimeError("Cannot set value on a cache with a loader")
        expires_at = time.time() + (ttl or self._ttl)
        self._store[key] = (expires_at, value)


def chunks(iterable: Iterable[T], size: int = 2) -> Iterator[list[T]]:
    if size <= 2:
        raise ValueError("Size must be > 2")

    batch: list[T] = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


async def achunks(aiterable: AsyncIterable[T], size: int = 2) -> AsyncIterator[list[T]]:
    if size <= 2:
        raise ValueError("Size must be > 2")

    batch: list[T] = []
    async for item in aiterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def is_guid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def raise_batch_errors(batch_payload: dict[str, Any], *, action: str) -> None:
    # Graph returns 200 for the batch envelope even if individual requests failed. :contentReference[oaicite:2]{index=2}
    for r in batch_payload.get("responses", []) or []:
        status = int(r.get("status", 0) or 0)
        if status >= 400:
            body = r.get("body")
            raise RuntimeError(f"Batch {action} failed (status={status}): {body}")
