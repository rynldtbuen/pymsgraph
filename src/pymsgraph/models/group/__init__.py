from __future__ import annotations

from typing import Any

from pymsgraph.models.directory_object import DirectoryObject
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    DateTimeField,
    Field,
    IntegerField,
    ListField,
    QuerySetField,
)
from pymsgraph.models.group.query_fields import MembersQuerySet
from pymsgraph.models.query import QuerySet


class Group(DirectoryObject):
    """
    Graph group resource type

    https://learn.microsoft.com/en-us/graph/api/resources/group?view=graph-rest-1.0
    """

    MICROSOFT365 = "microsoft365"
    DISTRIBUTION = "distribution"
    SECURITY = "security"
    SECURITY_MAIL_ENABLED = "security_mail_enabled"
    PATH = "/groups"
    SEARCH_FIELD = "display_name"

    # Properties
    allow_external_senders = BooleanField()
    assigned_labels = ListField()
    assigned_licenses = ListField()
    auto_subscribe_new_members = BooleanField()
    classification = CharField()
    created_date_time = DateTimeField()
    description = CharField()
    display_name = CharField(required=True, select_default=True)
    expiration_date_time = DateTimeField()
    group_types = ListField(select_default=True)
    has_members_with_license_errors = BooleanField()
    hide_from_address_lists = BooleanField()
    hide_from_outlook_clients = BooleanField()
    is_archived = BooleanField()
    is_assignable_to_role = BooleanField()
    is_management_restricted = BooleanField()
    is_subscribed_by_mail = BooleanField()
    license_processing_state = Field()
    mail = CharField(select_default=True)
    mail_enabled = BooleanField(required=True, select_default=True)
    mail_nickname = CharField(required=True)
    membership_rule = CharField()
    membership_rule_processing_state = CharField()
    on_premises_domain_name = CharField()
    on_premises_last_sync_date_time = DateTimeField()
    on_premises_net_bios_name = CharField()
    on_premises_provisioning_errors = ListField()
    on_premises_sam_account_name = CharField()
    on_premises_security_identifier = CharField()
    on_premises_sync_enabled = BooleanField()
    preferred_data_location = CharField()
    preferred_language = CharField()
    proxy_addresses = ListField()
    renewed_date_time = DateTimeField()
    security_enabled = BooleanField(required=True, select_default=True)
    security_identifier = CharField()
    service_provisioning_errors = ListField()
    theme = CharField()
    unique_name = CharField()
    unseen_count = IntegerField()
    visibility = CharField()

    # Navigation properties
    # TODO: accepted_senders = ListField()
    # TODO: app_role_assignments = ListField()
    # TODO: calendar = Field()
    # TODO: calendar_view = ListField()
    # TODO: conversations = ListField()
    # TODO: created_on_behalf_of = Field()
    # TODO: drive = Field()
    # TODO: drives = ListField()
    # TODO: events = ListField()
    # TODO: extensions = ListField()
    # TODO: group_lifecycle_policies = ListField()
    # TODO: member_of = ListField()
    members = QuerySetField(MembersQuerySet, model_class="User", prefetch=True)
    # TODO: members_with_license_errors = ListField()
    # TODO: on_premises_sync_behavior = Field()
    # TODO: onenote = Field()
    # TODO: owners = ListField()
    # TODO: permission_grants = ListField()
    # TODO: photo = Field()
    # TODO: photos = ListField()
    # TODO: planner = Field()
    # TODO: rejected_senders = ListField()
    # TODO: settings = ListField()
    # TODO: sites = ListField()
    # TODO: team = Field()
    # TODO: threads = ListField()
    # TODO: transitive_member_of = ListField()
    # TODO: transitive_members = ListField()

    @property
    def group_type(self) -> str:
        gtypes = {*(self.group_types or [])}
        has_unified = "Unified" in gtypes
        mail = bool(self.mail_enabled)
        security = bool(self.security_enabled)

        if has_unified:
            return "microsoft365"
        if mail and security:
            return "security_mail_enabled"
        if security and not mail:
            return "security"
        if mail and not security:
            return "distribution"
        return "unknown"

    def __repr__(self) -> str:
        return f"<Group: {self.display_name}, type={self.group_type}>"


class GroupQuerySet(QuerySet["Group"]):
    model_class = Group

    async def create_security_group(
        self,
        *,
        display_name: str,
        mail_nickname: str,
        mail_enabled: bool = False,
        **kwargs: Any,
    ) -> Group:
        return await self.create(
            display_name=display_name,
            mail_enabled=mail_enabled,
            mail_nickname=mail_nickname,
            security_enabled=True,
            **kwargs,
        )

    async def create_m365_group(
        self, *, display_name: str, mail_nickname: str, visibility: str, **kwargs: Any
    ) -> Group:
        return await self.create(
            display_name=display_name,
            mail_enabled=True,
            mail_nickname=mail_nickname,
            security_enabled=False,
            group_types=["Unified"],
            visibility=visibility,
            **kwargs,
        )


#     @property
#     def endpoint(self) -> str:
#         return f"{self._kwargs['group'].get_endpoint()}/members"

# def add(self, *users: "str | User | QuerySet['User']") -> None:
#     """
#     Add one or many users to this group.

#     Fast path:
#       PATCH /groups/{id} with members@odata.bind (up to 20 per call). :contentReference[oaicite:3]{index=3}
#     """
#     user_ids = utils.coerce_ids(*users)
#     if not user_ids:
#         return

#     client = self.model._get_client()
#     group = self._kwargs["group"]

#     # Graph supports adding up to 20 members per PATCH via members@odata.bind.
#     for chunk in utils.chunks(user_ids, 20):
#         binds = [f"{client.base_url}/directoryObjects/{uid}" for uid in chunk]
#         client.patch(
#             group.get_endpoint(),
#             json_body={"members@odata.bind": binds},
#         )

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
