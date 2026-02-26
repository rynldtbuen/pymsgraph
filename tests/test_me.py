from typing import TYPE_CHECKING

import httpx
import pytest

from pymsgraph.models.user import Me

if TYPE_CHECKING:
	from tests.conftest import MakeClient


def test_client_me_basic_paths(make_client: "MakeClient") -> None:
	def handler(request: httpx.Request) -> httpx.Response:
		raise AssertionError("No HTTP call expected")

	c, _ = make_client(handler)
	me = c.me

	assert isinstance(me, Me)
	assert me.path == "/me"
	assert me.messages.path == "/me/messages"
	assert me.drive.path == "/me/drive"


@pytest.mark.asyncio
async def test_client_me_get(make_client: "MakeClient") -> None:
	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == "GET" and request.url.path == "/v1.0/me":
			return httpx.Response(
				200,
				json={
					"id": "u1",
					"displayName": "Ada Lovelace",
					"userPrincipalName": "ada@contoso.com",
					"mailNickname": "ada",
					"accountEnabled": True,
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	c, _ = make_client(handler)
	me = await c.me.get()

	assert isinstance(me, Me)
	assert me.id == "u1"
	assert me.display_name == "Ada Lovelace"
	assert me.user_principal_name == "ada@contoso.com"
	assert me.path == "/me"
