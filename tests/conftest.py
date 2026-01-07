from functools import partial
import json
from typing import Any, Callable, TypeAlias
import pytest
import httpx

from pymsgraph.client import Client
from pymsgraph.models.query import Context, QuerySet
from pymsgraph.models.user import User


class FakeTokenProvider:
    def get_access_token(self, scopes=None) -> str:
        return "fake-token"


@pytest.fixture
def fake_token_provider() -> FakeTokenProvider:
    return FakeTokenProvider()


Handler: TypeAlias = Callable[[httpx.Request], httpx.Response]
CapturedRequest: TypeAlias = list[dict[str, Any]]
MakeClient: TypeAlias = Callable[[Handler], tuple[Client, CapturedRequest]]


@pytest.fixture
def make_client(fake_token_provider: Any) -> MakeClient:
    """
    Build a Client with a provided httpx.MockTransport handler.
    """

    def _make(handler: Handler) -> tuple[Client, CapturedRequest]:
        requests: list[dict] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            # capture request for assertions
            body = None
            if request.content:
                try:
                    body = json.loads(request.content.decode())
                except Exception:
                    body = request.content.decode()

            requests.append(
                {
                    "method": request.method,
                    "url": str(request.url),
                    "path": request.url.path,
                    "body": body,
                    "headers": dict(request.headers),
                }
            )
            return handler(request)

        transport = httpx.MockTransport(_handler)
        http = httpx.AsyncClient(transport=transport)
        client = Client(fake_token_provider, http=http)
        return client, requests

    return _make


@pytest.fixture
def user_qs(make_client):
    """
    Convenience fixture: a QuerySet for User with a no-op transport.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    client, _ = make_client(handler)
    ctx = Context(client=client, model_class=User, endpoint="/users")
    return QuerySet(ctx)
