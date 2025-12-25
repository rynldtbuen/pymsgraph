from functools import partial
import json
import pytest
import httpx

from pymsgraph.client import Client
from pymsgraph.models.user import User, UserQuerySet


class FakeTokenProvider:
    def get_access_token(self, scopes=None) -> str:
        return "fake-token"


@pytest.fixture
def fake_token_provider() -> FakeTokenProvider:
    return FakeTokenProvider()


@pytest.fixture
def make_client(fake_token_provider):
    """
    Build a Client with a provided httpx.MockTransport handler.
    """

    def _make(handler) -> tuple[Client, list[dict]]:
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
        http = httpx.Client(transport=transport)
        client = Client(fake_token_provider, http=http)
        return client, requests

    return _make


@pytest.fixture
def user_qs(make_client):
    """
    Convenience fixture: a UserQuerySet with a no-op transport.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    client, _ = make_client(handler)
    return UserQuerySet(client)
