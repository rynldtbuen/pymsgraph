from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING, Any

from pymsgraph import utils
from pymsgraph.models.directory_object import DirectoryObject
from pymsgraph.models.drive import Drive
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
from pymsgraph.models.subscribed_sku import SubscribedSku

from .common import EmployeeOrgData, PasswordProfile
from .query import (
    AppRoleAssignmentQuerySet,
    AppRoleAssignmentsQuerySetProxy,
    AssignedLicensesQuerySet,
    AssignedLicensesQuerySetProxy,
    AssignedPlansQuerySet,
    MemberOfQuerySet,
)

if TYPE_CHECKING:
    from pathlib import Path


class User(DirectoryObject):
    """
    Graph user resource type.

    https://learn.microsoft.com/en-us/graph/api/resources/user
    """

    PATH = "/users"
    SEARCH_FIELD = "display_name"

    # Properties
    about_me = CharField()
    account_enabled = BooleanField(default=True, required=True, select_default=True)
    age_group = CharField()
    assigned_licenses = QuerySetField(AssignedLicensesQuerySet)
    assigned_plans = QuerySetField(AssignedPlansQuerySet)
    authorization_info = Field()
    birthday = DateTimeField()
    business_phones = ListField()
    city = CharField()
    company_name = CharField()
    consent_provided_for_minor = CharField()
    country = CharField()
    created_date_time = DateTimeField()
    creation_type = CharField()
    custom_security_attributes = Field()
    department = CharField()
    device_enrollment_limit = IntegerField()
    display_name = CharField(required=True, select_default=True, order_by=True)
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
    im_addresses = ListField()
    interests = ListField()
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
    other_mails = ListField()
    password_policies = CharField()
    password_profile = ModelField(PasswordProfile, write_only=True)
    past_projects = ListField()
    postal_code = CharField()
    preferred_data_location = CharField()
    preferred_language = CharField()
    preferred_name = CharField()
    print = Field()
    provisioned_plans = ListField()
    proxy_addresses = ListField()
    responsibilities = ListField()
    schools = ListField()
    security_identifier = CharField()
    service_provisioning_errors = ListField()
    show_in_address_list = BooleanField()
    sign_in_activity = Field()
    sign_in_sessions_valid_from_date_time = DateTimeField()
    skills = ListField()
    state = CharField()
    street_address = CharField()
    surname = CharField()
    usage_location = CharField()
    user_principal_name = EmailField(required=True, select_default=True, order_by=True)
    user_type = CharField()

    # Navigation properties
    # TODO: activities = ListField()
    # TODO: agreement_acceptances = ListField()
    app_role_assignments = QuerySetField(AppRoleAssignmentQuerySet)
    # TODO: authentication = Field()
    # TODO: calendar = Field()
    # TODO: calendar_groups = ListField()
    # TODO: calendar_view = ListField()
    # TODO: calendars = ListField()
    # TODO: chats = ListField()
    # TODO: cloud_clipboard = Field()
    # TODO: cloud_pcs = ListField()
    # TODO: contact_folders = ListField()
    # TODO: contacts = ListField()
    # TODO: created_objects = ListField()
    # TODO: data_security_and_governance = Field()
    # TODO: device_management_troubleshooting_events = ListField()
    direct_reports = ListField(item_type="User", expand=True)
    # TODO: drives = ListField()
    # TODO: employee_experience = Field()
    # TODO: events = ListField()
    # TODO: extensions = ListField()
    # TODO: followed_sites = ListField()
    # TODO: inference_classification = Field()
    # TODO: insights = Field()
    # TODO: joined_teams = ListField()
    # TODO: license_details = ListField()
    # TODO: mail_folders = ListField()
    # TODO: managed_app_registrations = ListField()
    # TODO: managed_devices = ListField()
    manager = ModelField("User", expand=True)
    member_of = QuerySetField(MemberOfQuerySet, prefetch=True, expand=True)
    # TODO: messages = ListField()
    # TODO: oauth2_permission_grants = ListField()
    # TODO: onenote = Field()
    # TODO: online_meetings = ListField()
    # TODO: outlook = Field()
    # TODO: owned_devices = ListField()
    # TODO: owned_objects = ListField()
    # TODO: people = ListField()
    # TODO: permission_grants = ListField()
    # TODO: photo = Field()
    # TODO: photos = ListField()
    # TODO: planner = Field()
    # TODO: presence = Field()
    # TODO: registered_devices = ListField()
    # TODO: scoped_role_member_of = ListField()
    # TODO: settings = Field()
    # TODO: solutions = Field()
    # TODO: sponsors = ListField()
    # TODO: teamwork = Field()
    # TODO: todo = Field()
    # TODO: transitive_member_of = ListField()

    @property
    def path(self) -> str:
        if self.id is None and self.user_principal_name:
            return f"{self.PATH}/{self.user_principal_name}"
        return super().path

    @property
    def drive(self) -> Drive:
        return Drive(client=self._args[0], path=f"{self.path}/drive")

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

        path = self.path
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

        await self._client.patch(path, body=body)

    async def assign_manager(self, manager_id: str) -> None:
        """
        Assign a manager to this user.
        """

        if "@" in manager_id and not utils.is_guid(manager_id):
            manager_id = await self._client.users._cache.get(manager_id) or ""
            if manager_id is None:
                manager = await self._client.users.get(id=manager_id)
                if manager.id is None:
                    raise ValueError(
                        f"Unable to resolve manager id from '{manager_id}'."
                    )
                manager_id = manager.id
        body = {"@odata.id": f"{self._client.base_url}/directoryObjects/{manager_id}"}
        await self._client.put(f"{self.path}/manager/$ref", body=body)

    async def revoke_sign_in_sessions(self):
        return await self._client.post(f"{self.path}/revokeSignInSessions")

    def get_generated_password(self) -> str | None:
        pwd = getattr(self, "__generated_password", None)
        setattr(self, "__generated_password", None)
        return pwd

    @property
    def directory_object_id(self) -> str:
        if not self.id:
            raise ValueError(f"{type(self)} object id is missing.")
        return self.id


class UserQuerySet(QuerySet["User"]):
    model_class = User

    @property
    def _cache(self) -> utils.SimpleCache:
        if self._client is not None and hasattr(self._client, "_user_cache"):
            return getattr(self._client, "_user_cache")

        cache = utils.SimpleCache()
        if self._client is not None:
            setattr(self._client, "_user_cache", cache)
        return cache

    @property
    def assigned_licenses(self) -> AssignedLicensesQuerySetProxy:
        return AssignedLicensesQuerySetProxy(self)

    @property
    def app_role_assignments(self) -> AppRoleAssignmentsQuerySetProxy:
        return AppRoleAssignmentsQuerySetProxy(self)

    async def get(self, id: str | None = None, **kwargs: Any) -> "User":
        user = await super().get(id, **kwargs)
        if user.user_principal_name and user.id:
            self._cache.set(user.user_principal_name.lower(), user.id, ttl=86400)
        return user

    async def assign_manager(self, manager: "str | User | DirectoryObject") -> None:
        """
        Assign manager to all users in this queryset (batched).
        """

        if isinstance(manager, (User, DirectoryObject)):
            manager_id = getattr(manager, "id", None)
        else:
            manager_id = manager

        if not manager_id:
            raise ValueError("Manager id is required.")

        c = self._client
        manager_ref = {"@odata.id": f"{c.base_url}/directoryObjects/{manager_id}"}

        async for chunked_users in utils.achunks(self.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for i, u in enumerate(chunked_users, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "PUT",
                        "url": f"{u.path}/manager/$ref",
                        "headers": {"Content-Type": "application/json"},
                        "body": manager_ref,
                    }
                )
            batch_resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="assign manager to users")

    async def reset_password(
        self,
        path: "str | Path",
        *,
        password: str | None = None,
        auto_generate_password: bool = False,
        force_change_password_next_sign_in: bool = True,
        force_change_password_next_sign_in_with_mfa: bool | None = None,
    ) -> None:
        """
        Reset passwords for all users in this queryset (batched) and export to CSV.
        """

        import csv
        from pathlib import Path

        if not password and not auto_generate_password:
            raise ValueError(
                "'password' is required when resetting passwords. "
                "Set auto_generate_password=True to generate one per user."
            )

        out_path = Path(path)
        fieldnames = (
            "password",
            "display_name",
            "user_principal_name",
            "mobile_phone",
            "id",
        )

        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            qs = self.select(*fieldnames[1:])

            async for chunked_users in utils.achunks(qs, 20):
                requests: list[dict[str, Any]] = []
                for i, u in enumerate(chunked_users, start=1):
                    password_profile = PasswordProfile(
                        password=password or utils.generate_password(14),
                        force_change_password_next_sign_in=force_change_password_next_sign_in,
                        force_change_password_next_sign_in_with_mfa=force_change_password_next_sign_in_with_mfa,
                    )
                    requests.append(
                        {
                            "id": str(i),
                            "method": "PATCH",
                            "url": u.path,
                            "headers": {"Content-Type": "application/json"},
                            "body": {"passwordProfile": password_profile.serialize()},
                        }
                    )
                    writer.writerow(
                        {
                            "password": password_profile.password,
                            "display_name": u.display_name,
                            "user_principal_name": u.user_principal_name,
                            "mobile_phone": u.mobile_phone,
                            "id": u.id,
                        }
                    )

                batch_resp = await self._client.post(
                    "/$batch", body={"requests": requests}
                )
                utils.raise_batch_errors(batch_resp, action="reset user passwords")

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
        assign_licenses: str | Collection[str] | None = None,
        manager: str | None = None,
        **kwargs: Any,
    ) -> "User":

        if password is None:
            if not auto_generate_password:
                raise ValueError(
                    "'password' is required when creating a user. Set auto_generate_password=True to let the system create a random password for this user."
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
            path=self.path,
            **kwargs,
        )

        setattr(obj, "__generated_password", password)

        obj._validate_for_create()
        data = await self._client.post(self.path, body=obj.serialize())

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

        if manager is not None:
            await obj.assign_manager(manager)
        if assign_licenses is not None:
            if isinstance(assign_licenses, (str, bytes)) or not isinstance(
                assign_licenses, Collection
            ):
                assign_licenses = (assign_licenses,)

            resolved: list[str] = []
            for item in assign_licenses:
                if utils.is_guid(item):
                    resolved.append(item)
                else:
                    sku_id = SubscribedSku.get_sku_id(product_name=item)
                    if sku_id is not None:
                        resolved.append(sku_id)
                    else:
                        raise ValueError(f"Unknown license: {item!r}")
            if resolved:
                await obj.assigned_licenses.add(*resolved)

        return obj
