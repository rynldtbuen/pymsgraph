from __future__ import annotations

import secrets
import string
from collections.abc import Iterable as AbcIterable
from typing import Any, Callable, Iterable, Iterator, TypeVar

from pymsgraph.query import QuerySet


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


def chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def coerce_ids(*args: Any) -> list[str]:
    """
    Flatten *args of:
      - "user-id" strings
      - User objects
      - QuerySet[User] / iterables of the above
    into a deduped list of directoryObject ids.
    """

    def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in items:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    ids: list[str] = []

    def add_one(x: Any) -> None:
        if x is None:
            return

        # string id
        if isinstance(x, str):
            ids.append(x)
            return

        # QuerySet or any other iterable (but not strings)
        if isinstance(x, QuerySet):
            for item in x:
                add_one(item)
            return

        # assume User-like model instance
        # (your User has get_directory_object_id(), which resolves id if needed)
        if hasattr(x, "get_id"):
            ids.append(x.get_id())  # type: ignore
            return

        raise TypeError(f"Unsupported member type: {type(x)!r}")

    for arg in args:
        add_one(arg)

    return _dedupe_keep_order(ids)


def raise_batch_errors(batch_payload: dict[str, Any], *, action: str) -> None:
    # Graph returns 200 for the batch envelope even if individual requests failed. :contentReference[oaicite:2]{index=2}
    for r in batch_payload.get("responses", []) or []:
        status = int(r.get("status", 0) or 0)
        if status >= 400:
            body = r.get("body")
            raise RuntimeError(f"Batch {action} failed (status={status}): {body}")


T = TypeVar("T")


def coerce_values(
    *args: Any,
    resolver: Callable[[Any], T] | None = None,
    attr_names: tuple[str, ...] = (),
    allow_str: bool = True,
) -> list[T]:
    """
    Generic: flatten args -> resolve each item -> dedupe_keep_order.

    - resolver: custom extraction function
    - attr_names: fallbacks for objects (e.g. ("sku_id","skuId","id"))
    - allow_str: if True and T is str-like, pass strings through
    """

    def _dedupe_keep_order(items: AbcIterable[T]) -> list[T]:
        seen: set[T] = set()
        out: list[T] = []
        for x in items:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    def _is_iterable_but_not_str(x: Any) -> bool:
        return isinstance(x, AbcIterable) and not isinstance(
            x, (str, bytes, bytearray, dict)
        )

    def _flatten_args(*args: Any) -> Iterator[Any]:
        """Flatten QuerySets and iterables (lists/tuples/sets/etc) but not strings/dicts."""

        for x in args:
            if x is None:
                continue

            if isinstance(x, QuerySet):
                for item in x:
                    yield item
                continue

            if _is_iterable_but_not_str(x):
                for item in x:
                    yield item
                continue

            yield x

    out: list[T] = []

    for x in _flatten_args(*args):
        if allow_str and isinstance(x, str):
            out.append(x)  # type: ignore[arg-type]
            continue

        if resolver is not None:
            out.append(resolver(x))
            continue

        # attr-based extraction fallback
        got = False
        for name in attr_names:
            if hasattr(x, name):
                out.append(getattr(x, name))
                got = True
                break

        if got:
            continue

        raise TypeError(f"Unsupported value type: {type(x)!r}")

    return _dedupe_keep_order(out)
