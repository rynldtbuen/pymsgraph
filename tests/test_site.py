from __future__ import annotations

import httpx
import pytest

from pymsgraph.models.site import Site


def test_site_get_by_id_short_circuits(make_graph):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1.0/sites/site_123"
        return httpx.Response(
            200,
            json={
                "id": "site_123",
                "displayName": "Marketing",
                "name": "Marketing",
                "webUrl": "https://example.sharepoint.com/sites/Marketing",
                "siteCollection": {"hostname": "example.sharepoint.com"},
            },
        )

    make_graph(handler)

    s = Site.objects.get(id="site_123")
    assert s.id == "site_123"
    assert s.display_name == "Marketing"


def test_site_get_by_path_discovers_hostname_and_encodes_path(make_graph):
    calls: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.raw_path)

        # 1) discovery call
        if request.url.path == "/v1.0/sites/root":
            return httpx.Response(
                200,
                json={"siteCollection": {"hostname": "example.sharepoint.com"}},
            )

        # 2) site-by-path call (note: httpx decodes .url.path, so assert raw_path)
        assert request.method == "GET"
        assert request.url.raw_path == (
            b"/v1.0/sites/example.sharepoint.com:/sites/Marketing%20Team"
        )

        return httpx.Response(
            200,
            json={
                "id": "site_marketing",
                "displayName": "Marketing Team",
                "name": "Marketing Team",
                "webUrl": "https://example.sharepoint.com/sites/MarketingTeam",
                "siteCollection": {"hostname": "example.sharepoint.com"},
            },
        )

    make_graph(handler)

    # no leading slash on purpose (code should normalize + encode)
    s = Site.objects.get(path="sites/Marketing Team")
    assert s.id == "site_marketing"
    assert s.display_name == "Marketing Team"

    # sanity: discovery + fetch happened
    assert calls[0] == b"/v1.0/sites/root"
    assert calls[1].startswith(b"/v1.0/sites/example.sharepoint.com:/sites/")


def test_site_get_by_path_uses_cached_hostname_after_first_discovery(make_graph):
    call_no = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_no
        call_no += 1

        if call_no == 1:
            assert request.url.path == "/v1.0/sites/root"
            return httpx.Response(
                200,
                json={"siteCollection": {"hostname": "example.sharepoint.com"}},
            )

        if call_no == 2:
            assert (
                request.url.raw_path == b"/v1.0/sites/example.sharepoint.com:/sites/A"
            )
            return httpx.Response(200, json={"id": "site_a", "displayName": "A"})

        if call_no == 3:
            # should NOT re-call /sites/root
            assert (
                request.url.raw_path == b"/v1.0/sites/example.sharepoint.com:/sites/B"
            )
            return httpx.Response(200, json={"id": "site_b", "displayName": "B"})

        raise AssertionError("Unexpected extra request")

    make_graph(handler)

    a = Site.objects.get(path="/sites/A")
    b = Site.objects.get(path="sites/B")

    assert a.id == "site_a"
    assert b.id == "site_b"
    assert call_no == 3  # root discovery happened once


def test_site_get_rejects_unknown_lookups(make_graph):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    make_graph(handler)

    with pytest.raises(TypeError):
        Site.objects.get(path="/sites/Marketing", foo="bar")  # unsupported lookup


def test_site_get_requires_exactly_one_selector(make_graph):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    make_graph(handler)

    with pytest.raises(TypeError):
        Site.objects.get()  # neither id nor path

    with pytest.raises(TypeError):
        Site.objects.get(id="x", path="/sites/x")  # both provided


def test_site_get_path_root_is_not_supported(make_graph):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    make_graph(handler)

    with pytest.raises(TypeError):
        Site.objects.get(path="/")


def test_site_search_calls_sites_endpoint_with_search_param(make_graph):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1.0/sites"
        assert dict(request.url.params) == {"search": "Marketing"}
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "s1",
                        "displayName": "Marketing",
                        "webUrl": "https://example.sharepoint.com/sites/Marketing",
                        "siteCollection": {"hostname": "example.sharepoint.com"},
                    }
                ]
            },
        )

    make_graph(handler)

    sites = Site.objects.search("Marketing")
    assert len(sites) == 1
    assert sites[0].id == "s1"
    assert sites[0].display_name == "Marketing"


def test_site_filter_is_not_supported(make_graph):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP should not be called")

    make_graph(handler)

    with pytest.raises(ValueError):
        # Site.capabilities.filter = False, so QuerySet.filter should raise
        list(Site.objects.filter(display_name__startswith="A"))
