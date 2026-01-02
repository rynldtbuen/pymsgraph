from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pymsgraph import utils
from pymsgraph.fields import (
    BooleanField,
    CharField,
    QuerySetField,
    DateTimeField,
    EmailField,
    Field,
)
from pymsgraph.models.base import Model
from pymsgraph.query import Capabilities, QuerySet

from . import query


__all__ = ["UserQuerySet"]


class User(Model):
    """
    Graph user resource type.

    https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0
    """

    display_name = CharField(required=True)
    account_enabled = BooleanField(default=True)
    mail_nickname = CharField(required=True)
    user_principal_name = EmailField(required=True)

    about_me = CharField()
    age_group = CharField()
    assigned_licenses: query.AssignedLicensesQuerySet = QuerySetField(
        query.AssignedLicensesQuerySet
    )  # pyright: ignore[reportAssignmentType]
    assigned_plans = Field(read_only=True)
    birthday = DateTimeField()
    business_phones = Field()
    city = CharField(max_length=128)
    company_name = CharField()
    consent_provided_for_minor = CharField()
    country = CharField()
    created_date_time = DateTimeField(read_only=True)
    creation_type = CharField()
    custom_security_attributes = Field()
    department = CharField()
    employee_hire_date = DateTimeField()
    employee_id = CharField()
    employee_org_data = Field()
    employee_type = CharField()
    fax_number = CharField()
    given_name = CharField()
    hire_date = DateTimeField()
    identities = Field()
    im_addresses = Field()
    job_title = CharField()
    mail = EmailField(read_only=True)
    mobile_phone = CharField()
    interests = Field()
    office_location = CharField()
    is_management_restricted = BooleanField()
    is_resource_account = BooleanField()
    legal_age_group_classification = CharField()
    license_assignment_states = Field(read_only=True)
    last_password_change_date_time = DateTimeField(read_only=True)
    mailbox_settings = Field(read_only=True)
    my_site = CharField()
    on_premises_distinguished_name = CharField()
    on_premises_domain_name = CharField()
    on_premises_extension_attributes = Field()
    on_premises_immutable_id = CharField()
    on_premises_last_sync_date_time = DateTimeField(read_only=True)
    on_premises_provisioning_errors = Field(read_only=True)
    on_premises_sam_account_name = CharField()
    on_premises_security_identifier = CharField(read_only=True)
    on_premises_sync_enabled = BooleanField()
    on_premises_user_principal_name = CharField()
    other_mails = Field()
    password_policies = CharField()
    password_profile = Field(read_only=True)
    past_projects = Field()
    postal_code = CharField()
    preferred_data_location = CharField()
    preferred_language = CharField()
    preferred_name = CharField()
    provisioned_plans = Field(read_only=True)
    proxy_addresses = Field()
    responsibilities = Field()
    schools = Field()
    security_identifier = CharField(read_only=True)
    service_provisioning_errors = Field(read_only=True)
    show_in_address_list = BooleanField()
    sign_in_activity = Field(read_only=True)
    sign_in_sessions_valid_from_date_time = DateTimeField(read_only=True)
    skills = Field()
    state = CharField()
    street_address = CharField()
    surname = CharField()
    usage_location = CharField()
    user_type = CharField()

    # Relationship
    member_of = QuerySetField(query.MemberOfQuerySet)

    search_field = "display_name"
    endpoint = "/users"
    supported_lookup = query.supported_lookup

    def __repr__(self):
        return f"<User: {self.display_name}>"

    def save(self) -> bool:
        if self.id is None:
            raise ValueError("User is not initialized or does not exist")

        payload = self.to_graph(for_update=True)
        if not payload:
            return False

        self._client.patch(self.endpoint, json_body=payload)
        self._dirty.clear()
        return True

    def reset_password(
        self,
        *,
        password: str | None = None,
        force_change_password_next_sign_in: bool = True,
        force_change_password_next_sign_in_with_mfa: bool | None = None,
        auto_generate_password: bool = False,
    ) -> None:

        if self.id is None:
            raise ValueError("Cannot reset password for an unsaved User (missing id)")

        # reset stash each call
        self._generated_password = None

        if auto_generate_password and not password:
            password = utils.generate_password(14)
            self._generated_password = password

        if not password:
            raise ValueError(
                "'password' is required when resetting a user's password. "
                "Set auto_generate_password=True to generate one."
            )

        body = PasswordProfile(
            password=password,
            force_change_password_next_sign_in=force_change_password_next_sign_in,
            force_change_password_next_sign_in_with_mfa=force_change_password_next_sign_in_with_mfa,
        ).to_graph()

        self._client.patch(self.endpoint, json_body=body)

    def revoke_sign_in_sessions(self):
        return self._client.post(f"{self.endpoint}/revokeSignInSessions")

    def get_generated_password(self) -> str | None:
        """Return the auto-generated password (if any) and clear it immediately.

        This is ONLY available in-memory right after creation. Graph will never return it.
        """
        pwd = getattr(self, "_generated_password", None)
        self._generated_password = None
        return pwd

    def delete(self, *, force: bool = False) -> None:
        if not force:
            raise RuntimeError(
                "Refusing to delete User without confirmation. "
                "Call delete(force=True) to proceed."
            )

        self._client.delete(self.endpoint)

        # Local cleanup (object represents a deleted remote resource)
        self._data.clear()
        self._dirty.clear()


class UserQuerySet(QuerySet["User"]):
    model_class = User
    capabilities = Capabilities.read_write(search=True)

    # @property
    # def groups(self) -> groups.GroupsBulkQuerySet:
    #     return groups.GroupsBulkQuerySet(self)

    # @property
    # def assigned_license(self) -> assigned_licenses.LicensesBulkQuerySet:
    #     return assigned_licenses.LicensesBulkQuerySet(self)

    def get_by_directory_ids(
        self,
        *ids: str | Iterable[str],
    ) -> list["User"]:
        """
        Resolve directory object IDs to users via /directoryObjects/getByIds.
        """
        id_list: list[str] = []
        for arg in ids:
            if isinstance(arg, str):
                id_list.append(arg)
            else:
                id_list.extend(list(arg))
        if not id_list:
            return []

        results: list[User] = []
        for chunk in utils.chunks(id_list, 1000):
            payload = {"ids": list(chunk), "types": ["user"]}
            data = self._client.post("/directoryObjects/getByIds", json_body=payload)
            results.extend(
                self.model_class(graph_data=item, parent=self)
                for item in data.get("value", [])
            )
        return results

    def create(
        self,
        *,
        display_name: str,
        user_principal_name: str,
        mail_nickname: str,
        account_enabled: bool = True,
        password: str | None = None,
        force_change_password_next_sign_in: bool = True,
        auto_generate_password: bool = False,
        **kwargs: Any,
    ) -> "User":
        if password is None:
            if not auto_generate_password:
                raise ValueError(
                    "'password' is required when creasting a user. Set auto_generate_password=True to let the system create a random password for this user."
                )
            password = utils.generate_password(14)

        obj = self.model_class(
            display_name=display_name,
            user_principal_name=user_principal_name,
            mail_nickname=mail_nickname,
            account_enabled=account_enabled,
            parent=self,
            **kwargs,
        )
        obj._validate_for_create()
        payload = obj.to_graph(for_update=False)
        payload.update(
            PasswordProfile(
                password=password,
                force_change_password_next_sign_in=force_change_password_next_sign_in,
            ).to_graph()
        )
        obj.refresh_from_graph(self._client.post(self.endpoint, json_body=payload))
        return obj

    def _prefetch_related(self, objs: list[User]) -> None:
        if "licenses" not in self._select_related:
            return

        rel = getattr(self.model_class, "licenses", None)
        graph_name = getattr(rel, "graph_name", "licenseDetails")

        users = [u for u in objs if getattr(u, "id", None)]
        if not users:
            return

        for batch in utils.chunks(users, 20):
            requests: list[dict[str, Any]] = []
            id_map: dict[str, User] = {}
            for idx, u in enumerate(batch, start=1):
                req_id = str(idx)
                id_map[req_id] = u
                requests.append(
                    {
                        "id": req_id,
                        "method": "GET",
                        "url": f"{u.endpoint}/{graph_name}",
                    }
                )

            resp = self._client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="prefetch user licenses")

            for r in resp.get("responses", []) or []:
                req_id = str(r.get("id", ""))
                user = id_map.get(req_id)
                if not user:
                    continue
                body = r.get("body") or {}
                user._data["licenses"] = body.get("value", [])

    def enabled_with_assigned_licenses(self):
        return


class PasswordProfile(Model):
    is_read_only = True
    password = CharField(read_only=True)
    force_change_password_next_sign_in = BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = BooleanField(read_only=True)

    def to_graph(self, *, for_update: bool = False) -> dict[str, Any]:
        return {"passwordProfile": super().to_graph(for_update=False)}
