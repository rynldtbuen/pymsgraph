from __future__ import annotations

from typing import Any

from pymsgraph import utils
from pymsgraph.models.base import Model
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    DateTimeField,
    EmailField,
    Field,
    IntegerField,
    ListField,
    ModelField,
    QuerySetField,
)
from pymsgraph.models.query import QuerySet

from .model_fields import (
    AssignedLicensesQuerySet,
    EmployeeOrgData,
    MemberOfQuerySet,
    PasswordProfile,
    AssignedPlansQuerySet,
)


class User(Model):
    """
    Graph user resource type.

    https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0
    """

    # Properties
    about_me = CharField()
    account_enabled = BooleanField(default=True, required=True, select_default=True)
    age_group = CharField()
    assigned_licenses = QuerySetField(AssignedLicensesQuerySet)
    assigned_plans = QuerySetField(AssignedPlansQuerySet)
    authorization_info = Field()
    birthday = DateTimeField()
    business_phones = ListField(item_type=str)
    city = CharField()
    company_name = CharField()
    consent_provided_for_minor = CharField()
    country = CharField()
    created_date_time = DateTimeField()
    creation_type = CharField()
    custom_security_attributes = Field()
    department = CharField()
    device_enrollment_limit = IntegerField()
    display_name = CharField(required=True, select_default=True)
    employee_hire_date = DateTimeField()
    employee_id = CharField()
    employee_leave_date_time = DateTimeField()
    employee_org_data = ModelField(EmployeeOrgData)
    employee_type = CharField()
    external_user_state = CharField()
    external_user_state_change_date_time = DateTimeField()
    fax_number = CharField()
    given_name = CharField()
    hire_date = DateTimeField()
    identities = ListField()
    im_addresses = ListField(item_type=str)
    interests = ListField(item_type=str)
    is_management_restricted = BooleanField()
    is_resource_account = BooleanField()
    job_title = CharField()
    last_password_change_date_time = DateTimeField()
    legal_age_group_classification = CharField()
    license_assignment_states = ListField()
    mail = EmailField(read_only=True, select_default=True)
    mail_nickname = CharField(required=True)
    mailbox_settings = Field()
    mobile_phone = CharField()
    my_site = CharField()
    office_location = CharField()
    on_premises_distinguished_name = CharField()
    on_premises_domain_name = CharField()
    on_premises_extension_attributes = Field()
    on_premises_immutable_id = CharField()
    on_premises_last_sync_date_time = DateTimeField()
    on_premises_provisioning_errors = ListField()
    on_premises_sam_account_name = CharField()
    on_premises_security_identifier = CharField()
    on_premises_sync_enabled = BooleanField()
    on_premises_user_principal_name = CharField()
    other_mails = ListField(item_type=str)
    password_policies = CharField()
    password_profile = ModelField(PasswordProfile, write_only=True)
    past_projects = ListField(item_type=str)
    postal_code = CharField()
    preferred_data_location = CharField()
    preferred_language = CharField()
    preferred_name = CharField()
    print = Field()
    provisioned_plans = ListField()
    proxy_addresses = ListField(item_type=str)
    responsibilities = ListField(item_type=str)
    schools = ListField(item_type=str)
    security_identifier = CharField()
    service_provisioning_errors = ListField()
    show_in_address_list = BooleanField()
    sign_in_activity = Field()
    sign_in_sessions_valid_from_date_time = DateTimeField()
    skills = ListField(item_type=str)
    state = CharField()
    street_address = CharField()
    surname = CharField()
    usage_location = CharField()
    user_principal_name = EmailField(required=True, select_default=True)
    user_type = CharField()

    # # Navigation properties
    # activities = ListField()
    # agreement_acceptances = ListField()
    # app_role_assignments = ListField()
    # authentication = Field()
    # calendar = Field()
    # calendar_groups = ListField()
    # calendar_view = ListField()
    # calendars = ListField()
    # chats = ListField()
    # cloud_clipboard = Field()
    # cloud_pcs = ListField()
    # contact_folders = ListField()
    # contacts = ListField()
    # created_objects = ListField()
    # data_security_and_governance = Field()
    # device_management_troubleshooting_events = ListField()
    # direct_reports = ListField()
    # drive = Field()
    # drives = ListField()
    # employee_experience = Field()
    # events = ListField()
    # extensions = ListField()
    # followed_sites = ListField()
    # inference_classification = Field()
    # insights = Field()
    # joined_teams = ListField()
    # license_details = ListField()
    # mail_folders = ListField()
    # managed_app_registrations = ListField()
    # managed_devices = ListField()
    # manager = Field()
    member_of = QuerySetField(MemberOfQuerySet, model_class="Group")
    # messages = ListField()
    # oauth2_permission_grants = ListField()
    # onenote = Field()
    # online_meetings = ListField()
    # outlook = Field()
    # owned_devices = ListField()
    # owned_objects = ListField()
    # people = ListField()
    # permission_grants = ListField()
    # photo = Field()
    # photos = ListField()
    # planner = Field()
    # presence = Field()
    # registered_devices = ListField()
    # scoped_role_member_of = ListField()
    # settings = Field()
    # solutions = Field()
    # sponsors = ListField()
    # teamwork = Field()
    # todo = Field()
    # transitive_member_of = ListField()

    def __repr__(self):
        return f"<User: {self.id}, {self.display_name}, {self.user_principal_name}>"

    async def reset_password(
        self,
        *,
        password: str | None = None,
        force_change_password_next_sign_in: bool = True,
        force_change_password_next_sign_in_with_mfa: bool | None = None,
        auto_generate_password: bool = False,
    ) -> None:

        ep = self._endpoint
        self._generated_password = None

        if auto_generate_password and not password:
            password = utils.generate_password(14)
            self._generated_password = password

        if not password:
            raise ValueError(
                "'password' is required when resetting a user's password. "
                "Set auto_generate_password=True to generate one."
            )

        body = self.FIELDS["password_profile"].to_graph(
            {
                "password": password,
                "force_change_password_next_sign_in": force_change_password_next_sign_in,
                "force_change_password_next_sign_in_with_mfa": force_change_password_next_sign_in_with_mfa,
            }
        )

        await self._client.patch(ep, body=body)

    def revoke_sign_in_sessions(self):
        return self._client.post(f"{self._endpoint}/revokeSignInSessions")

    def get_generated_password(self) -> str | None:
        """Return the auto-generated password (if any) and clear it immediately."""
        pwd = getattr(self, "_generated_password", None)
        self._generated_password = None
        return pwd

    async def delete(self, *, force: bool = False) -> None:
        if not force:
            raise RuntimeError("Call delete(force=True) to proceed.")

        await self._client.delete(self._endpoint)

        self._data.clear()
        self._dirty.clear()


class UserQuerySet(QuerySet["User"]):

    model_class = User
    #     capabilities = Capabilities.read_write(search=True)

    #     # @property
    #     # def groups(self) -> groups.GroupsBulkQuerySet:
    #     #     return groups.GroupsBulkQuerySet(self)

    #     # @property
    #     # def assigned_license(self) -> assigned_licenses.LicensesBulkQuerySet:
    #     #     return assigned_licenses.LicensesBulkQuerySet(self)

    #     def get_by_directory_ids(
    #         self,
    #         *ids: str | Iterable[str],
    #     ) -> list["User"]:
    #         """
    #         Resolve directory object IDs to users via /directoryObjects/getByIds.
    #         """
    #         id_list: list[str] = []
    #         for arg in ids:
    #             if isinstance(arg, str):
    #                 id_list.append(arg)
    #             else:
    #                 id_list.extend(list(arg))
    #         if not id_list:
    #             return []

    #         results: list[User] = []
    #         for chunk in utils.chunks(id_list, 1000):
    #             payload = {"ids": list(chunk), "types": ["user"]}
    #             data = self._client.post("/directoryObjects/getByIds", json_body=payload)
    #             results.extend(
    #                 self.model_class(graph_data=item, parent=self)
    #                 for item in data.get("value", [])
    #             )
    #         return results

    async def create(
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

        obj = User(
            display_name=display_name,
            user_principal_name=user_principal_name,
            mail_nickname=mail_nickname,
            account_enabled=account_enabled,
            password_profile=dict(
                password=password,
                force_change_password_next_sign_in=force_change_password_next_sign_in,
            ),
            client=self._client,
            endpoint=self._endpoint,
            **kwargs,
        )
        obj._validate_for_create()
        data = await self._client.post(self._endpoint, body=obj.serialize())
        if data:
            merged = dict(data)
            for attr_name, val in obj._data.items():
                field = obj.FIELDS.get(attr_name)
                if field is None or field.write_only:
                    continue
                graph_attr_name = field.graph_attr_name or attr_name
                merged.setdefault(graph_attr_name, field.to_graph(val))
            data = merged
            obj.refresh_from_graph(data)
        return obj


#     def _prefetch_related(self, objs: list[User]) -> None:
#         if "licenses" not in self._select_related:
#             return

#         rel = getattr(self.model_class, "licenses", None)
#         graph_name = getattr(rel, "graph_name", "licenseDetails")

#         users = [u for u in objs if getattr(u, "id", None)]
#         if not users:
#             return

#         for batch in utils.chunks(users, 20):
#             requests: list[dict[str, Any]] = []
#             id_map: dict[str, User] = {}
#             for idx, u in enumerate(batch, start=1):
#                 req_id = str(idx)
#                 id_map[req_id] = u
#                 requests.append(
#                     {
#                         "id": req_id,
#                         "method": "GET",
#                         "url": f"{u.endpoint}/{graph_name}",
#                     }
#                 )

#             resp = self._client.post("/$batch", json_body={"requests": requests})
#             utils.raise_batch_errors(resp, action="prefetch user licenses")

#             for r in resp.get("responses", []) or []:
#                 req_id = str(r.get("id", ""))
#                 user = id_map.get(req_id)
#                 if not user:
#                     continue
#                 body = r.get("body") or {}
#                 user._data["licenses"] = body.get("value", [])

#     def enabled_with_assigned_licenses(self):
#         return
