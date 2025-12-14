from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    display_name = CharField(required=True, max_length=256, strip=True)
    mail_enabled = BooleanField(required=True)
    mail_nickname = CharField(required=True, max_length=64, strip=True)
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

    def add(self, directory_object_id: str) -> None:
        """Add *this user* to the group (POST /groups/{group-id}/members/$ref)."""
        client = self.model._get_client()

        # Graph expects a full @odata.id pointing at a directoryObject
        json_body = {
            "@odata.id": f"{client.base_url}/directoryObjects/{directory_object_id}"
        }
        client.post(f"{self.endpoint}/$ref", json_body=json_body)

    def remove(self, directory_object_id: str) -> None:
        """Remove *this user* from the group (DELETE /groups/{group-id}/members/{id}/$ref)."""
        client = self.model._get_client()
        client.delete(f"{self.endpoint}/{directory_object_id}/$ref")
