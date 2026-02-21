from __future__ import annotations

import logging
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
from pymsgraph.models.group.query import MembersQuerySet
from pymsgraph.models.query import QuerySet

_logger = logging.getLogger(__name__)


class Group(DirectoryObject):
    """
    Graph group resource.

    Reference:
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
    # accepted_senders = ListField()
    # app_role_assignments = ListField()
    # calendar = Field()
    # calendar_view = ListField()
    # conversations = ListField()
    # created_on_behalf_of = Field()
    # drive = Field()
    # drives = ListField()
    # events = ListField()
    # extensions = ListField()
    # group_lifecycle_policies = ListField()
    # member_of = ListField()
    members = QuerySetField(MembersQuerySet, model_class="User", prefetch=True)
    # members_with_license_errors = ListField()
    # on_premises_sync_behavior = Field()
    # onenote = Field()
    # owners = ListField()
    # permission_grants = ListField()
    # photo = Field()
    # photos = ListField()
    # planner = Field()
    # rejected_senders = ListField()
    # settings = ListField()
    # sites = ListField()
    # team = Field()
    # threads = ListField()
    # transitive_member_of = ListField()
    # transitive_members = ListField()

    @property
    def group_type(self) -> str:
        """
        Resolve the effective group category from Graph fields.

        Resolution order:
            1. `microsoft365` when `group_types` contains `"Unified"`
            2. `security_mail_enabled` when both `mail_enabled` and
               `security_enabled` are true
            3. `security` when only `security_enabled` is true
            4. `distribution` when only `mail_enabled` is true
            5. `unknown` otherwise

        Returns:
            str:
                One of:
                - `Group.MICROSOFT365`
                - `Group.SECURITY_MAIL_ENABLED`
                - `Group.SECURITY`
                - `Group.DISTRIBUTION`
                - `"unknown"`
        """
        gtypes = {*(self.group_types or [])}
        has_unified = "Unified" in gtypes
        mail = bool(self.mail_enabled)
        security = bool(self.security_enabled)

        if has_unified:
            group_type = "microsoft365"
        elif mail and security:
            group_type = "security_mail_enabled"
        elif security and not mail:
            group_type = "security"
        elif mail and not security:
            group_type = "distribution"
        else:
            group_type = "unknown"

        _logger.debug(
            "Group.group_type id=%s group_types=%s mail_enabled=%s security_enabled=%s resolved=%s",
            self.id,
            sorted(gtypes),
            mail,
            security,
            group_type,
        )
        return group_type

    def __repr__(self) -> str:
        return f"<Group: {self.display_name}, type={self.group_type}>"


class GroupQuerySet(QuerySet["Group"]):
    """
    QuerySet interface for working with Microsoft Graph groups.
    """

    model_class = Group

    async def create_security_group(
        self,
        *,
        display_name: str,
        mail_nickname: str,
        mail_enabled: bool = False,
        **kwargs: Any,
    ) -> Group:
        """
        Create a security group.

        This helper wraps `create(...)` with `security_enabled=True` and lets
        callers optionally choose whether the group is mail-enabled.

        Args:
            display_name:
                Group display name.
            mail_nickname:
                Mail nickname/alias.
            mail_enabled:
                Whether to create a mail-enabled security group.
                Defaults to `False`.
            **kwargs:
                Additional group fields accepted by Graph/model.

        Returns:
            Group:
                Created group model.

        Raises:
            ValueError:
                If required model fields are missing/invalid.
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.
        """
        _logger.debug(
            "GroupQuerySet.create_security_group display_name=%s mail_nickname=%s mail_enabled=%s extra=%s",
            display_name,
            mail_nickname,
            mail_enabled,
            sorted(kwargs.keys()),
        )
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
        """
        Create a Microsoft 365 (Unified) group.

        This helper wraps `create(...)` with defaults required for M365 groups:
        `group_types=["Unified"]`, `mail_enabled=True`, `security_enabled=False`.

        Args:
            display_name:
                Group display name.
            mail_nickname:
                Mail nickname/alias.
            visibility:
                Group visibility (for example `Public` or `Private`).
            **kwargs:
                Additional group fields accepted by Graph/model.

        Returns:
            Group:
                Created group model.

        Raises:
            ValueError:
                If required model fields are missing/invalid.
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.
        """
        _logger.debug(
            "GroupQuerySet.create_m365_group display_name=%s mail_nickname=%s visibility=%s extra=%s",
            display_name,
            mail_nickname,
            visibility,
            sorted(kwargs.keys()),
        )
        return await self.create(
            display_name=display_name,
            mail_enabled=True,
            mail_nickname=mail_nickname,
            security_enabled=False,
            group_types=["Unified"],
            visibility=visibility,
            **kwargs,
        )
