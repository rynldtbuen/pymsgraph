from __future__ import annotations

from pymsgraph.fields import BooleanField, CharField, DateTimeField, Field, IntegerField
from pymsgraph.models.base import Model
from pymsgraph.query import Capabilities, QuerySet

from . import lookups, members, owners


class Group(Model):
    # Required on create
    display_name = CharField(required=True)
    mail_enabled = BooleanField(required=True)
    mail_nickname = CharField(required=True)
    security_enabled = BooleanField(required=True)

    # Optional
    description = CharField()
    group_types = Field()
    visibility = CharField()

    allow_external_senders = BooleanField()
    assigned_labels = Field()
    assigned_licenses = Field(read_only=True)
    auto_subscribe_new_members = BooleanField()
    classification = CharField()
    created_date_time = DateTimeField(read_only=True)
    expiration_date_time = DateTimeField(read_only=True)
    has_members_with_license_errors = BooleanField()
    hide_from_address_lists = BooleanField()
    hide_from_outlook_clients = BooleanField()
    is_archived = BooleanField()
    is_assignable_to_role = BooleanField()
    is_management_restricted = BooleanField(read_only=True)
    is_subscribed_by_mail = BooleanField()
    license_processing_state = Field(read_only=True)
    mail = CharField(read_only=True)
    membership_rule = CharField()
    membership_rule_processing_state = CharField()
    on_premises_domain_name = CharField(read_only=True)
    on_premises_last_sync_date_time = DateTimeField(read_only=True)
    on_premises_net_bios_name = CharField(read_only=True)
    on_premises_provisioning_errors = Field()
    on_premises_sam_account_name = CharField(read_only=True)
    on_premises_security_identifier = CharField(read_only=True)
    on_premises_sync_enabled = BooleanField(read_only=True)
    preferred_data_location = CharField()
    preferred_language = CharField()
    proxy_addresses = Field(read_only=True)
    renewed_date_time = DateTimeField(read_only=True)
    security_identifier = CharField(read_only=True)
    service_provisioning_errors = Field()
    theme = CharField()
    unique_name = CharField(read_only=True)
    unseen_count = IntegerField()

    supported_lookup = lookups.supported_lookup
    endpoint = "/groups"

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
    def members(self) -> members.MembersQuerySet:
        qs = members.MembersQuerySet(self._client, parent=self)
        return qs

    @property
    def owners(self) -> owners.OwnersQuerySet:
        qs = owners.OwnersQuerySet(self._client, parent=self)
        return qs

    def __repr__(self) -> str:
        return f"<Group: {self.display_name}, type={self.group_type}"


class GroupQuerySet(QuerySet["Group"]):
    model_class = Group
    capabilities = Capabilities.read_write(search=True)

    # related_lookup = {"group_types": lookups._group_types}
    search_field = "display_name"

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
