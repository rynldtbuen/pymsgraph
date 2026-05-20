from __future__ import annotations

import configparser
import importlib
import json
from pathlib import Path
import re
import secrets
import string
import time
import tomllib
import uuid
from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Iterator, TypeVar

if TYPE_CHECKING:
    from pymsgraph.client import Client
    from pymsgraph.models.base import Model

T = TypeVar("T")


_SUPPORTED_CONFIG_EXTENSIONS: frozenset[str] = frozenset({"json", "toml", "ini", "cfg"})


def _normalize_config_ext(ext: str) -> str:
    normalized = (ext or "").strip().lower().lstrip(".")
    if not normalized:
        raise ValueError("Config extension is required.")
    if normalized not in _SUPPORTED_CONFIG_EXTENSIONS:
        supported = ", ".join(sorted(_SUPPORTED_CONFIG_EXTENSIONS))
        raise ValueError(
            f"Unsupported config extension: {ext!r}. Supported: {supported}"
        )
    return normalized


def _parse_ini_like(path: Path) -> dict[str, Any]:
    parser = configparser.ConfigParser()
    with path.open("r", encoding="utf-8") as f:
        parser.read_file(f)

    data: dict[str, Any] = {}
    if parser.defaults():
        data["DEFAULT"] = dict(parser.defaults())
    for section in parser.sections():
        data[section] = dict(parser[section].items())
    return data


def load_config(path: str | None = None, ext: str = "json") -> dict[str, Any]:
    """
    Load configuration from JSON, TOML, INI, or CFG files.

    Args:
        path:
            Explicit path to the config file. When omitted, defaults to
            `config.{ext}`.
        ext:
            Config extension/format. Supports `json`, `toml`, `ini`, `cfg`.
            If `path` has a recognized suffix, that suffix is used.

    Returns:
        dict[str, Any]:
            Parsed configuration dictionary.
    """
    fallback_ext = _normalize_config_ext(ext)
    _path = Path(path) if path is not None else Path(f"config.{fallback_ext}")

    if not _path.exists():
        raise FileNotFoundError(f"Missing configuration file: {_path}")

    suffix = _path.suffix.lower().lstrip(".")
    config_ext = (
        _normalize_config_ext(suffix)
        if suffix in _SUPPORTED_CONFIG_EXTENSIONS
        else fallback_ext
    )

    if config_ext == "json":
        with _path.open("r", encoding="utf-8") as f:
            return json.load(f)
    if config_ext == "toml":
        with _path.open("rb") as f:
            return tomllib.load(f)
    return _parse_ini_like(_path)


def to_datestr(val: datetime | str, astimezone: bool = True) -> str:
    if isinstance(val, str):
        val = datetime.fromisoformat(val)
    if astimezone:
        return val.astimezone().strftime("%d/%m/%Y")
    return val.strftime("%d/%m/%Y")


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
                return 0, None
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


_BATCH_MAX_SIZE = 20
_BATCH_ENDPOINT = "/$batch"
_BATCH_ALLOWED_METHODS: frozenset[str] = frozenset(
    {"GET", "POST", "PATCH", "PUT", "DELETE"}
)


def build_batch_requests(
    objects: Iterable["Model"],
    *,
    method: str = "PATCH",
    url: Callable[["Model"], str] | str | None = None,
    body: Callable[["Model"], dict[str, Any] | None] | None = None,
    headers: dict[str, str] | Callable[["Model"], dict[str, str]] | None = None,
    size: int = _BATCH_MAX_SIZE,
    start_id: int = 1,
) -> Iterator[list[dict[str, Any]]]:
    """
    Build Microsoft Graph `$batch` request payloads from iterable model objects.

    Iterates `objects`, derives a per-object Graph batch request entry
    (`id`, `method`, `url`, optional `headers`, optional `body`) and yields
    them grouped into chunks suitable for posting to `/$batch`.

    Args:
        objects:
            Iterable of `Model` instances to include in the batch.
        method:
            HTTP method for each request. One of `GET`, `POST`, `PATCH`,
            `PUT`, `DELETE`. Defaults to `PATCH`.
        url:
            Per-object URL resolver. Either a callable `obj -> str` or a
            literal URL string. When `None`, `obj.path` is used.
        body:
            Per-object body resolver `obj -> dict | None`. When `None`,
            the body is derived from `obj.serialize()` for write methods
            (`POST`/`PATCH`/`PUT`); omitted for `GET`/`DELETE`. Objects
            whose resolved body is empty/`None` are skipped for write
            methods.
        headers:
            Either a fixed `dict` applied to every request, or a callable
            `obj -> dict`. When omitted, no `headers` key is set on the
            request (Graph then uses the batch envelope defaults).
        size:
            Maximum number of requests per yielded chunk. Capped at the
            Graph batch limit of 20.
        start_id:
            Starting integer used for the `id` of the first request. The
            `id` increments across the whole iteration (not per chunk),
            keeping every request id unique.

    Yields:
        list[dict[str, Any]]:
            Lists of Graph batch request dicts, each list containing at
            most `size` entries (and never more than 20).

    Raises:
        ValueError:
            If `method` is unsupported or `size` is not positive.

    Example:
        ```python
        from pymsgraph import utils

        # Bulk PATCH: serialize dirty fields from each model
        async for chunk in utils.achunks(qs, 20):
            for requests in utils.build_batch_requests(
                chunk,
                method="PATCH",
                url=lambda o: f"{o.path}/fields",
                headers={"Content-Type": "application/json"},
            ):
                resp = await client.post("/$batch", body={"requests": requests})
                utils.raise_batch_errors(resp, requests, action="patch items")

        # Bulk DELETE
        for requests in utils.build_batch_requests(items, method="DELETE"):
            resp = await client.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(resp, requests, action="delete items")
        ```
    """
    m = (method or "").upper()
    if m not in _BATCH_ALLOWED_METHODS:
        allowed = ", ".join(sorted(_BATCH_ALLOWED_METHODS))
        raise ValueError(f"Unsupported batch method: {method!r}. Allowed: {allowed}")
    if size <= 0:
        raise ValueError("size must be > 0")
    chunk_size = min(size, _BATCH_MAX_SIZE)

    has_body = m in {"POST", "PATCH", "PUT"}

    def _resolve_url(obj: "Model") -> str:
        if url is None:
            return obj.path
        if callable(url):
            return url(obj)
        return url

    def _resolve_body(obj: "Model") -> dict[str, Any] | None:
        if not has_body:
            return None
        if body is not None:
            return body(obj)
        return obj.serialize()

    def _resolve_headers(obj: "Model") -> dict[str, str] | None:
        if headers is None:
            return None
        if callable(headers):
            return headers(obj)
        return dict(headers)

    batch: list[dict[str, Any]] = []
    next_id = start_id
    for obj in objects:
        request_body = _resolve_body(obj)
        if has_body and not request_body:
            continue

        entry: dict[str, Any] = {
            "id": str(next_id),
            "method": m,
            "url": _resolve_url(obj),
        }
        if (h := _resolve_headers(obj)) is not None:
            entry["headers"] = h
        if request_body is not None:
            entry["body"] = request_body

        batch.append(entry)
        next_id += 1

        if len(batch) == chunk_size:
            yield batch
            batch = []

    if batch:
        yield batch


async def send_batch_requests(
    client: "Client",
    objects: Iterable["Model"],
    *,
    method: str = "PATCH",
    url: Callable[["Model"], str] | str | None = None,
    body: Callable[["Model"], dict[str, Any] | None] | None = None,
    headers: dict[str, str] | Callable[["Model"], dict[str, str]] | None = None,
    size: int = _BATCH_MAX_SIZE,
    start_id: int = 1,
    action: str = "batch",
) -> AsyncIterator[tuple[list[dict[str, Any]], list[dict[str, Any]]]]:
    """
    Execute Microsoft Graph `$batch` requests built from iterable model objects.

    Thin async-generator orchestrator on top of `build_batch_requests`:
    builds per-chunk request payloads, posts each chunk to `/$batch`, runs
    `raise_batch_errors` on the response, and yields `(requests, responses)`
    so callers can perform post-success work (e.g. clearing `_dirty`,
    collecting created object bodies, counting).

    Args:
        client:
            `Client` instance used to POST each chunk to `/$batch`.
        objects:
            Iterable of `Model` instances to include in the batch.
        method:
            HTTP method for each request. See `build_batch_requests`.
        url:
            Per-object URL resolver. See `build_batch_requests`.
        body:
            Per-object body resolver. See `build_batch_requests`.
        headers:
            Per-request headers (dict or callable). See `build_batch_requests`.
        size:
            Maximum number of requests per chunk (capped at 20).
        start_id:
            Starting integer for the first request `id`. The id is monotonic
            across chunks.
        action:
            Human-readable label forwarded to `raise_batch_errors` for error
            messages (e.g. `"create list items"`).

    Yields:
        tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            Per chunk, the list of request entries that were sent and the
            list of `responses` returned by Graph (already validated by
            `raise_batch_errors`).

    Raises:
        ValueError:
            Propagated from `build_batch_requests` on bad `method`/`size`.
        httpx.HTTPStatusError:
            If the `$batch` envelope POST itself fails.
        RuntimeError:
            If any per-request response has `status >= 400`.

    Example:
        ```python
        from pymsgraph import utils

        # Bulk DELETE
        deleted = 0
        async for requests, _ in utils.send_batch_requests(
            client,
            items,
            method="DELETE",
            action="delete list items",
        ):
            deleted += len(requests)

        # Bulk PATCH with dirty-field clearing on success
        items_sent: list = []
        async for requests, _ in utils.send_batch_requests(
            client,
            field_value_sets,
            method="PATCH",
            url=lambda fvs: fvs.path,
            body=lambda fvs: {k: fvs._graph_data[k] for k in fvs._dirty},
            action="update list item fields (dirty)",
        ):
            # caller owns dirty-clearing after a successful send
            ...
        ```
    """
    for requests in build_batch_requests(
        objects,
        method=method,
        url=url,
        body=body,
        headers=headers,
        size=size,
        start_id=start_id,
    ):
        batch_resp = await client.post(
            _BATCH_ENDPOINT, body={"requests": requests}
        )
        raise_batch_errors(batch_resp, requests, action=action)
        yield requests, list(batch_resp.get("responses") or [])


def raise_batch_errors(
    batch_payload: dict[str, Any],
    requests: Iterable[dict[str, Any]] | None = None,
    *,
    action: str,
) -> None:
    # Graph returns 200 for the batch envelope even if individual requests failed.
    request_map: dict[str, dict[str, Any]] = {}
    if requests:
        for req in requests:
            req_id = req.get("id")
            if req_id is None:
                continue
            request_map[str(req_id)] = req

    for r in batch_payload.get("responses", []) or []:
        status = int(r.get("status", 0) or 0)
        if status >= 400:
            body = r.get("body")
            request_info: dict[str, Any] | None = None
            if request_map:
                req = request_map.get(str(r.get("id")))
                if req is not None:
                    request_info = {
                        "id": req.get("id"),
                        "method": req.get("method"),
                        "url": req.get("url"),
                        "body": req.get("body"),
                    }
            if request_info:
                raise RuntimeError(
                    f"Batch {action} failed (status={status}) "
                    f"for request {request_info}: {body}"
                )
            raise RuntimeError(f"Batch {action} failed (status={status}): {body}")
