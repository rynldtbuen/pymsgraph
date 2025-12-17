from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pymsgraph import utils
from pymsgraph.fields import BooleanField, CharField, Field
from pymsgraph.manager import BaseManager
from pymsgraph.models.base import GraphModel
from pymsgraph.queryset import QuerySet

if TYPE_CHECKING:
    from .user import User


class Group(GraphModel):
    """Microsoft Graph Group model.

    Create group required properties (Graph v1.0):
      - displayName
      - mailEnabled
      - mailNickname
      - securityEnabled
    """

    endpoint = "/groups"

    # Required on create
    display_name = CharField(required=True, max_length=256)
    mail_enabled = BooleanField(required=True)
    mail_nickname = CharField(required=True, max_length=100)
    security_enabled = BooleanField(required=True)

    # Optional
    description = CharField(max_length=1024, strip=True)
    group_types = Field()  # graph: groupTypes (list[str])
    visibility = CharField(max_length=20)

    @property
    def members(self):
        try:
            return self._members  # type: ignore
        except AttributeError:
            from .user import User

            members = BaseManager.from_queryset(_MembersQuerySet)(User, group=self)
            self._members = members
            return members


class _MembersQuerySet(QuerySet["User"]):
    @property
    def endpoint(self) -> str:
        return f"{self._kwargs['group'].get_endpoint()}/members"

    def add(self, *users: "str | User | QuerySet['User']") -> None:
        """
        Add one or many users to this group.

        Fast path:
          PATCH /groups/{id} with members@odata.bind (up to 20 per call). :contentReference[oaicite:3]{index=3}
        """
        user_ids = utils.coerce_ids(*users)
        if not user_ids:
            return

        client = self.model._get_client()
        group = self._kwargs["group"]

        # Graph supports adding up to 20 members per PATCH via members@odata.bind.
        for chunk in utils.chunks(user_ids, 20):
            binds = [f"{client.base_url}/directoryObjects/{uid}" for uid in chunk]
            client.patch(
                group.get_endpoint(),
                json_body={"members@odata.bind": binds},
            )

    def remove(self, *users: "str | User | QuerySet['User']") -> None:
        """
        Remove one or many users from this group.

        Uses:
          DELETE /groups/{id}/members/{member-id}/$ref :contentReference[oaicite:4]{index=4}
        Batched with POST /$batch (max 20 requests per batch). :contentReference[oaicite:5]{index=5}
        """
        user_ids = utils.coerce_ids(*users)
        if not user_ids:
            return

        client = self.model._get_client()
        group = self._kwargs["group"]

        # Batch delete refs (20 requests max per batch)
        for chunk in utils.chunks(user_ids, 20):
            requests: list[dict[str, Any]] = []
            for i, uid in enumerate(chunk, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "DELETE",
                        # batch urls must be relative like "/groups/..." :contentReference[oaicite:6]{index=6}
                        "url": f"{group.get_endpoint()}/members/{uid}/$ref",
                    }
                )

            batch_resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="remove members")
