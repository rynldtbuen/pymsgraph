from __future__ import annotations

from typing import Any, ClassVar

# from pymsgraph import utils
from pymsgraph.fields import BooleanField, CharField, Field
from pymsgraph.models.base import EndpointDescriptor, Model
from pymsgraph.models.group import compile_lookup
from pymsgraph.models.group.members import MembersQuerySet
from pymsgraph.query import Capabilities, QuerySet


class Group(Model):
    # Required on create
    display_name = CharField(required=True)
    mail_enabled = BooleanField(required=True)
    mail_nickname = CharField(required=True)
    security_enabled = BooleanField(required=True)

    # Optional
    description = CharField()
    group_types = Field()  # graph: groupTypes (list[str])
    visibility = CharField()

    endpoint = EndpointDescriptor("/groups")

    @property
    def group_type(self) -> str:
        """
        Classify the group based on Graph flags:
          - "microsoft365": groupTypes contains "Unified" (M365 group)
          - "mail_enabled_security": mailEnabled and securityEnabled
          - "security": securityEnabled only
          - "distribution": mailEnabled only (and not Unified)
          - "unknown": fallback when flags are inconclusive
        """
        gtypes = {*(self.group_types or [])}
        has_unified = "Unified" in gtypes
        mail = bool(self.mail_enabled)
        security = bool(self.security_enabled)

        if has_unified:
            return "microsoft365"
        if mail and security:
            return "mail_enabled_security"
        if security and not mail:
            return "security"
        if mail and not security:
            return "distribution"
        return "unknown"

    @property
    def members(self) -> MembersQuerySet:
        qs = MembersQuerySet(self.client, endpoint=f"{self.endpoint}/members")
        qs._obj = self
        return qs

    def __repr__(self) -> str:
        return f"<Group: {self.display_name}, type={self.group_type}"


class GroupQuerySet(QuerySet["Group"]):
    model_class = Group
    capabilities = Capabilities.read_write(search=True)

    related_lookup = {"group_types": compile_lookup._group_types}
    search_field = "display_namme"

    def create(
        self,
        *,
        display_name: str,
        mail_enabled: bool,
        mail_nickname: str,
        security_enabled: bool,
        **kwargs: Any,
    ) -> "Group":
        obj = self.model_class(
            display_name=display_name,
            mail_enabled=mail_enabled,
            mail_nickname=mail_nickname,
            security_enabled=security_enabled,
            qs=self,
            **kwargs,
        )
        obj._validate_for_create()
        payload = obj.to_graph(for_update=False)
        graph_data = self._client.post(self.endpoint, json_body=payload)
        obj.refresh_from_graph(graph_data)
        return obj

    @property
    def unified(self):
        return self.filter(group_types="Unified")


#     @property
#     def endpoint(self) -> str:
#         return f"{self._kwargs['group'].get_endpoint()}/members"

#     def add(self, *users: "str | User | QuerySet['User']") -> None:
#         """
#         Add one or many users to this group.

#         Fast path:
#           PATCH /groups/{id} with members@odata.bind (up to 20 per call). :contentReference[oaicite:3]{index=3}
#         """
#         user_ids = utils.coerce_ids(*users)
#         if not user_ids:
#             return

#         client = self.model._get_client()
#         group = self._kwargs["group"]

#         # Graph supports adding up to 20 members per PATCH via members@odata.bind.
#         for chunk in utils.chunks(user_ids, 20):
#             binds = [f"{client.base_url}/directoryObjects/{uid}" for uid in chunk]
#             client.patch(
#                 group.get_endpoint(),
#                 json_body={"members@odata.bind": binds},
#             )

#     def remove(self, *users: "str | User | QuerySet['User']") -> None:
#         """
#         Remove one or many users from this group.

#         Uses:
#           DELETE /groups/{id}/members/{member-id}/$ref :contentReference[oaicite:4]{index=4}
#         Batched with POST /$batch (max 20 requests per batch). :contentReference[oaicite:5]{index=5}
#         """
#         user_ids = utils.coerce_ids(*users)
#         if not user_ids:
#             return

#         client = self.model._get_client()
#         group = self._kwargs["group"]

#         # Batch delete refs (20 requests max per batch)
#         for chunk in utils.chunks(user_ids, 20):
#             requests: list[dict[str, Any]] = []
#             for i, uid in enumerate(chunk, start=1):
#                 requests.append(
#                     {
#                         "id": str(i),
#                         "method": "DELETE",
#                         # batch urls must be relative like "/groups/..." :contentReference[oaicite:6]{index=6}
#                         "url": f"{group.get_endpoint()}/members/{uid}/$ref",
#                     }
#                 )

#             batch_resp = client.post("/$batch", json_body={"requests": requests})
#             utils.raise_batch_errors(batch_resp, action="remove members")
