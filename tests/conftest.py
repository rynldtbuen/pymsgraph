from __future__ import annotations

# pytest automatically discovers this file and makes its fixtures available to
# all tests in this directory tree.

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import httpx
import pytest

from pymsgraph.client import GraphClient


@dataclass(slots=True)
class DummyTokenProvider:
    """Minimal token provider for tests.

    GraphClient only needs an object with `get_access_token(scopes=...) -> str`.
    """

    token: str = "TEST_TOKEN"

    def get_access_token(
        self, scopes: Sequence[str] | None = None
    ) -> str:  # noqa: ARG002
        # Tests don't care about scopes; they care that auth header exists.
        return self.token


@pytest.fixture
def make_graph(
    request: pytest.FixtureRequest,
) -> Callable[[Callable[[httpx.Request], httpx.Response]], GraphClient]:
    """Factory fixture: create a GraphClient wired to an httpx.MockTransport handler.

    Key idea:
      - Each test passes a handler(request)->response, so it can assert request details.
      - We register teardown finalizers so the http client is always closed, even
        when assertions fail (so tests don't need try/finally).
    """

    def _make(handler: Callable[[httpx.Request], httpx.Response]) -> GraphClient:
        # MockTransport routes all outgoing requests to our handler.
        transport = httpx.MockTransport(handler)

        # We create an httpx.Client ourselves so we can inject the transport.
        # Register it for teardown so the test doesn't need to close it manually.
        http = httpx.Client(transport=transport)
        request.addfinalizer(http.close)

        # Build the GraphClient using the injected httpx client.
        graph = GraphClient(
            DummyTokenProvider(),
            http=http,
            base_url="https://graph.microsoft.com/v1.0",
        )

        # Make this client the default for all GraphModel subclasses used in this test.
        graph.configure_default()

        # Defensive cleanup: after the test, clear the default client if it still points
        # to this graph (which will now have a closed httpx.Client).
        from pymsgraph.models.base import GraphModel

        def _reset_default_client() -> None:
            if GraphModel._default_client is graph:  # type: ignore[attr-defined]
                GraphModel._default_client = None  # type: ignore[attr-defined]

        request.addfinalizer(_reset_default_client)

        return graph

    return _make
