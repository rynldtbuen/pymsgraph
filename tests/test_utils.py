from __future__ import annotations

import re
from typing import Any

import httpx
import pytest

from pymsgraph.utils import (
    build_batch_requests,
    load_config,
    send_batch_requests,
)


class _FakeModel:
    """Minimal stand-in for `Model` used by batch-builder tests."""

    def __init__(self, path: str, payload: dict[str, Any] | None = None) -> None:
        self.path = path
        self._payload = payload if payload is not None else {}

    def serialize(self) -> dict[str, Any]:
        return dict(self._payload)


# ---------------------------------------------------------------------------
# build_batch_requests
# ---------------------------------------------------------------------------


def test_build_batch_requests_patch_uses_serialize_and_defaults():
    objs = [
        _FakeModel("/items/1", {"Title": "A"}),
        _FakeModel("/items/2", {"Title": "B"}),
    ]

    chunks = list(build_batch_requests(objs))

    assert len(chunks) == 1
    requests = chunks[0]
    assert requests == [
        {"id": "1", "method": "PATCH", "url": "/items/1", "body": {"Title": "A"}},
        {"id": "2", "method": "PATCH", "url": "/items/2", "body": {"Title": "B"}},
    ]


def test_build_batch_requests_skips_empty_body_for_write_methods():
    objs = [
        _FakeModel("/items/1", {"Title": "A"}),
        _FakeModel("/items/2", {}),  # empty -> skipped
        _FakeModel("/items/3", {"Title": "C"}),
    ]

    requests = list(build_batch_requests(objs))[0]

    assert [r["url"] for r in requests] == ["/items/1", "/items/3"]
    # ids remain monotonic, skipped object does not consume an id
    assert [r["id"] for r in requests] == ["1", "2"]


def test_build_batch_requests_delete_omits_body_and_uses_callable_url():
    objs = [_FakeModel("/items/1"), _FakeModel("/items/2")]

    requests = list(
        build_batch_requests(
            objs, method="DELETE", url=lambda o: f"{o.path}/x"
        )
    )[0]

    assert requests == [
        {"id": "1", "method": "DELETE", "url": "/items/1/x"},
        {"id": "2", "method": "DELETE", "url": "/items/2/x"},
    ]
    for r in requests:
        assert "body" not in r
        assert "headers" not in r


def test_build_batch_requests_headers_dict_and_callable():
    objs = [_FakeModel("/items/1", {"x": 1}), _FakeModel("/items/2", {"x": 2})]

    static = list(build_batch_requests(objs, headers={"H": "v"}))[0]
    assert all(r["headers"] == {"H": "v"} for r in static)

    dynamic = list(
        build_batch_requests(
            objs, headers=lambda o: {"P": o.path}
        )
    )[0]
    assert [r["headers"] for r in dynamic] == [{"P": "/items/1"}, {"P": "/items/2"}]


def test_build_batch_requests_body_callable_and_start_id():
    objs = [_FakeModel("/items/1"), _FakeModel("/items/2")]

    requests = list(
        build_batch_requests(
            objs,
            method="POST",
            body=lambda o: {"path": o.path},
            start_id=10,
        )
    )[0]

    assert [r["id"] for r in requests] == ["10", "11"]
    assert [r["body"] for r in requests] == [{"path": "/items/1"}, {"path": "/items/2"}]


def test_build_batch_requests_chunks_capped_at_20():
    objs = [_FakeModel(f"/items/{i}", {"v": i}) for i in range(25)]

    chunks = list(build_batch_requests(objs, size=100))

    assert [len(c) for c in chunks] == [20, 5]
    # ids monotonic across chunks
    assert chunks[0][0]["id"] == "1"
    assert chunks[1][0]["id"] == "21"


def test_build_batch_requests_custom_size():
    objs = [_FakeModel(f"/items/{i}", {"v": i}) for i in range(7)]

    chunks = list(build_batch_requests(objs, size=3))

    assert [len(c) for c in chunks] == [3, 3, 1]


def test_build_batch_requests_invalid_method():
    with pytest.raises(ValueError, match="Unsupported batch method"):
        list(build_batch_requests([], method="OPTIONS"))


def test_build_batch_requests_invalid_size():
    with pytest.raises(ValueError, match="size must be > 0"):
        list(build_batch_requests([], size=0))


def test_build_batch_requests_empty_iterable_yields_nothing():
    assert list(build_batch_requests([])) == []


# ---------------------------------------------------------------------------
# send_batch_requests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_batch_requests_posts_and_yields_responses(make_client):
    captured_bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "responses": [
                    {"id": "1", "status": 200, "body": {"ok": 1}},
                    {"id": "2", "status": 200, "body": {"ok": 2}},
                ]
            },
        )

    client, requests_log = make_client(handler)
    objs = [_FakeModel("/items/1", {"a": 1}), _FakeModel("/items/2", {"a": 2})]

    async with client as c:
        chunks = []
        async for reqs, resps in send_batch_requests(
            c, objs, method="PATCH", action="t"
        ):
            chunks.append((reqs, resps))
            captured_bodies.append(requests_log[-1]["body"])

    assert len(chunks) == 1
    reqs, resps = chunks[0]
    assert [r["url"] for r in reqs] == ["/items/1", "/items/2"]
    assert [r["status"] for r in resps] == [200, 200]
    # posted to /$batch with the requests envelope
    assert requests_log[-1]["path"].endswith("/$batch")
    assert captured_bodies[-1] == {"requests": reqs}


@pytest.mark.asyncio
async def test_send_batch_requests_raises_on_failed_subrequest(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "responses": [
                    {"id": "1", "status": 500, "body": {"error": "boom"}},
                ]
            },
        )

    client, _ = make_client(handler)
    objs = [_FakeModel("/items/1", {"a": 1})]

    async with client as c:
        with pytest.raises(RuntimeError, match="Batch t failed"):
            async for _ in send_batch_requests(c, objs, method="PATCH", action="t"):
                pass


@pytest.mark.asyncio
async def test_send_batch_requests_multi_chunk(make_client):
    posts: list[list[dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        body = _json.loads(request.content.decode())
        posts.append(body["requests"])
        return httpx.Response(
            200,
            json={
                "responses": [
                    {"id": r["id"], "status": 204} for r in body["requests"]
                ]
            },
        )

    client, _ = make_client(handler)
    objs = [_FakeModel(f"/items/{i}") for i in range(25)]

    async with client as c:
        n_chunks = 0
        total = 0
        async for reqs, _resps in send_batch_requests(
            c, objs, method="DELETE", action="del"
        ):
            n_chunks += 1
            total += len(reqs)

    assert n_chunks == 2
    assert total == 25
    assert [len(p) for p in posts] == [20, 5]
    # monotonic ids across chunks
    assert posts[0][0]["id"] == "1"
    assert posts[1][0]["id"] == "21"


def test_load_config_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"tenant": "contoso", "retry": 3}', encoding="utf-8")

    cfg = load_config(str(path))

    assert cfg == {"tenant": "contoso", "retry": 3}


def test_load_config_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[graph]\nbase_url = "https://graph.microsoft.com/v1.0"\n',
        encoding="utf-8",
    )

    cfg = load_config(str(path))

    assert cfg == {"graph": {"base_url": "https://graph.microsoft.com/v1.0"}}


@pytest.mark.parametrize("suffix", ["ini", "cfg"])
def test_load_config_ini_like(tmp_path, suffix):
    path = tmp_path / f"config.{suffix}"
    path.write_text(
        "[auth]\nclient_id = abc\ntenant = contoso\n",
        encoding="utf-8",
    )

    cfg = load_config(str(path))

    assert cfg == {"auth": {"client_id": "abc", "tenant": "contoso"}}


def test_load_config_uses_default_filename_from_ext(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text('[app]\nname = "pymsgraph"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    cfg = load_config(ext="toml")

    assert cfg == {"app": {"name": "pymsgraph"}}


def test_load_config_path_without_suffix_uses_ext(tmp_path):
    path = tmp_path / "config"
    path.write_text('[section]\nvalue = "x"\n', encoding="utf-8")

    cfg = load_config(str(path), ext="toml")

    assert cfg == {"section": {"value": "x"}}


def test_load_config_rejects_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported config extension"):
        load_config(ext="yaml")


def test_load_config_missing_file_raises(tmp_path):
    path = tmp_path / "missing.toml"

    with pytest.raises(FileNotFoundError, match=re.escape(str(path))):
        load_config(str(path), ext="toml")
