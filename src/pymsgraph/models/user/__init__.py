from __future__ import annotations

import logging
from collections.abc import Collection
from typing import TYPE_CHECKING, Any, Self

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
from .common import Authentication, EmployeeOrgData, PasswordProfile
from .mail_folder import MailFolderQuerySet
from .message import MessageQuerySet
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

_logger = logging.getLogger(__name__)


class User(DirectoryObject):
    """
    Graph user resource.

    Reference:
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
    # activities = ListField()
    # agreement_acceptances = ListField()
    app_role_assignments = QuerySetField(AppRoleAssignmentQuerySet)
    authentication = ModelField(Authentication, is_proxy=True)
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
    direct_reports = ListField(item_type="User", expand=True)
    # drives = ListField()
    # employee_experience = Field()
    # events = ListField()
    # extensions = ListField()
    # followed_sites = ListField()
    # inference_classification = Field()
    # insights = Field()
    # joined_teams = ListField()
    # license_details = ListField()
    mail_folders = QuerySetField(MailFolderQuerySet, prefetch=True)
    # managed_app_registrations = ListField()
    # managed_devices = ListField()
    manager = ModelField("User", expand=True)
    member_of = QuerySetField(MemberOfQuerySet, prefetch=True, expand=True)

    messages = QuerySetField(MessageQuerySet, prefetch=True)
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

    @property
    def path(self) -> str:
        """
        Resolve the Graph path for this user instance.

        Returns:
                str:
                        `/users/{id}` when `id` is available; otherwise
                        `/users/{user_principal_name}` when only UPN is set.
        """
        if self.id is None and self.user_principal_name:
            return f"{self.PATH}/{self.user_principal_name}"
        return super().path

    @property
    def drive(self) -> Drive:
        """
        Return a `Drive` model bound to this user's default drive endpoint.

        Returns:
                Drive:
                        Drive model targeting `{user.path}/drive`.
        """
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
        as_batch_request: bool = False,
        request_id: str | None = None,
    ) -> None | dict[str, Any]:
        """
        Reset this user's password.

        Args:
                password:
                        New password to set. Required unless
                        `auto_generate_password=True`.
                force_change_password_next_sign_in:
                        Whether the user must change password at next sign-in.
                force_change_password_next_sign_in_with_mfa:
                        Whether the user must change password at next sign-in with MFA.
                auto_generate_password:
                        Generate a random password when `password` is not provided.
                as_batch_request:
                        When `True`, return a Graph `$batch` request payload instead
                        of executing the request immediately.
                request_id:
                        Optional batch request id used when `as_batch_request=True`.

        Returns:
                None | dict[str, Any]:
                        `None` when the PATCH request is executed directly, otherwise
                        a `$batch` request dictionary.

        Raises:
                ValueError:
                        If `password` is missing and `auto_generate_password` is `False`.
                httpx.HTTPStatusError:
                        If Graph returns an HTTP error for direct mode.

        Notes:
                Generated passwords are stored temporarily and can be retrieved once
                via `get_generated_password()`.
        """
        _logger.debug(
            "User.reset_password user=%s batch=%s",
            self.id or self.user_principal_name,
            as_batch_request,
        )

        path = self.path

        if auto_generate_password and not password:
            password = utils.generate_password(14)

        if not password:
            raise ValueError(
                "'password' is required when resetting a user's password. "
                "Set auto_generate_password=True to generate one."
            )

        setattr(self, "__generated_password", password)

        password_profile = PasswordProfile(
            password=password,
            force_change_password_next_sign_in=force_change_password_next_sign_in,
            force_change_password_next_sign_in_with_mfa=force_change_password_next_sign_in_with_mfa,
        )

        if as_batch_request:
            _logger.debug("User.reset_password batch request for %s", path)
            return {
                "id": request_id,
                "method": "PATCH",
                "url": self.path,
                "headers": {"Content-Type": "application/json"},
                "body": {"passwordProfile": password_profile.serialize()},
            }

        _logger.debug("User.reset_password patch %s", path)
        await self._client.patch(path, body=password_profile.serialize())

    async def assign_manager(
        self,
        manager_id: str,
        as_batch_request: bool = False,
        request_id: str | None = None,
    ) -> None | dict[str, Any]:
        """
        Assign a manager to this user.

        Args:
                manager_id:
                        Manager object id or resolvable UPN/email.
                as_batch_request:
                        When `True`, return a Graph `$batch` request payload instead
                        of executing the request.
                request_id:
                        Optional batch request id used when `as_batch_request=True`.

        Returns:
                None | dict[str, Any]:
                        `None` when the request is executed directly, otherwise
                        a `$batch` request dictionary.

        Raises:
                ValueError:
                        If manager UPN/email cannot be resolved to an object id.
                httpx.HTTPStatusError:
                        If Graph returns an HTTP error for direct mode.
        """
        _logger.debug(
            "User.assign_manager user=%s manager_id=%s batch=%s",
            self.id or self.user_principal_name,
            manager_id,
            as_batch_request,
        )

        if "@" in manager_id and not utils.is_guid(manager_id):
            cache_manager_id = await self._client.users._cache.get(manager_id) or ""
            if cache_manager_id:
                manager_id = cache_manager_id
            else:
                manager = await self._client.users.get(id=manager_id)
                if manager.id is None:
                    raise ValueError(
                        f"Unable to resolve manager id from '{manager_id}'."
                    )
                manager_id = manager.id

        body = {"@odata.id": f"{self._client.base_url}/directoryObjects/{manager_id}"}

        if as_batch_request:
            _logger.debug("User.assign_manager batch request for %s", self.path)
            return {
                "id": request_id,
                "method": "PUT",
                "url": f"{self.path}/manager/$ref",
                "headers": {"Content-Type": "application/json"},
                "body": body,
            }
        _logger.debug("User.assign_manager put %s", self.path)
        await self._client.put(f"{self.path}/manager/$ref", body=body)

    async def revoke_sign_in_sessions(self):
        """
        Revoke refresh tokens and sign-in sessions for this user.

        Returns:
                Any:
                        Graph response payload from `POST {user.path}/revokeSignInSessions`.

        Raises:
                httpx.HTTPStatusError:
                        If Graph returns an HTTP error.
        """
        _logger.debug(
            "User.revoke_sign_in_sessions user=%s", self.id or self.user_principal_name
        )
        # TODO: return None
        return await self._client.post(f"{self.path}/revokeSignInSessions")

    def get_generated_password(self) -> str | None:
        """
        Return the last generated password and clear it from memory.

        Returns:
                str | None:
                        Generated password if available; otherwise `None`.

        Notes:
                This is a one-time accessor. After reading, the stored value is reset.
        """
        pwd = getattr(self, "__generated_password", None)
        setattr(self, "__generated_password", None)
        return pwd

    @property
    def directory_object_id(self) -> str:
        """
        Return the directory object id for this user.

        Returns:
                str:
                        User object id.

        Raises:
                ValueError:
                        If `id` is not set on this model instance.
        """
        if not self.id:
            raise ValueError(f"{type(self)} object id is missing.")
        return self.id


class Me(User):
    """
    Graph `me` endpoint modeled as the signed-in delegated user.

    Reference:
    https://learn.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0&tabs=http#http-request
    """

    PATH = "/me"

    @property
    def path(self) -> str:
        """
        Return the `me` endpoint path.

        Returns:
                str:
                        `/me` (or bound custom path when provided).
        """
        return self._args[1] or self.PATH  # pyright: ignore[reportReturnType]

    async def get(self) -> "Me":
        """
        Fetch the signed-in user from `/me`.

        Returns:
                Me:
                        Hydrated `Me` model.
        """
        data = await self._client.get(self.path)
        return Me.from_graph(data=data, client=self._client, path=self.path)

    def __repr__(self):
        return f"<Me: {self.id}, {self.display_name}, {self.user_principal_name}>"


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
        """
        Bulk license operations for users in this queryset.

        Returns:
                AssignedLicensesQuerySetProxy:
                        Proxy exposing `add(...)` and `remove(...)` for license
                        assignment/removal for all users in this queryset.
        """
        return AssignedLicensesQuerySetProxy(self)

    @property
    def app_role_assignments(self) -> AppRoleAssignmentsQuerySetProxy:
        return AppRoleAssignmentsQuerySetProxy(self)

    def by_id(self, id: str) -> User:
        return User(client=self._args[0], id=id)

    async def get(self, id: str | None = None, **kwargs: Any) -> "User":
        """
        Retrieve a single user by id/UPN or unique filter criteria.

        This wraps `QuerySet.get(...)` and adds a cache side effect: when a user
        has both `user_principal_name` and `id`, the mapping
        `user_principal_name.lower() -> id` is cached for 24 hours.

        Args:
                id:
                        Optional user id or UPN. When provided, lookup is done via
                        `GET /users/{id}`.
                **kwargs:
                        Field filters used for lookup when `id` is not provided.
                        Expected to match exactly one user.

        Returns:
                User:
                        The resolved user object.

        Raises:
                ValueError:
                        If both `id` and `kwargs` are missing.
                DoesNotExist:
                        If no user matches the provided filters.
                MultipleObjectsReturned:
                        If filter lookup matches more than one user.
                httpx.HTTPStatusError:
                        If Microsoft Graph returns an HTTP error.

        Notes:
                - Cache key: `user_principal_name.lower()`
                - Cache TTL: 86400 seconds (24 hours)

        Quick usage:
                ```python
                user = await client.users.get(id="alice@contoso.com")
                user = await client.users.get(mail="alice@contoso.com")
                ```
        """
        _logger.debug("UserQuerySet.get id=%s kwargs=%s", id, kwargs)
        user = await super().get(id, **kwargs)
        if user.user_principal_name and user.id:
            self._cache.set(user.user_principal_name.lower(), user.id, ttl=86400)
        return user

    async def assign_manager(self, manager_id: str) -> None:
        """
        Assign a manager to all users in this queryset.

        Users are processed in Microsoft Graph `$batch` requests of up to 20 items.
        Each user contributes a `PUT /users/{id}/manager/$ref` request through
        `User.assign_manager(..., as_batch_request=True)`.

        Args:
                manager_id:
                        Manager directory object ID or UPN/email. UPN values are resolved
                        per user request before the manager reference is submitted.

        Returns:
                None

        Raises:
                ValueError:
                        If `manager_id` is empty.
                httpx.HTTPStatusError:
                        If Microsoft Graph returns an error for any batch request.

        Notes:
                - Batch failures are surfaced via `utils.raise_batch_errors(...)`.
                - If the queryset is empty, no Graph requests are sent.

        Quick usage:
                ```python
                await client.users.filter(department="IT").assign_manager(
                        "manager@contoso.com"
                )
                ```
        """

        if not manager_id:
            raise ValueError("Manager id is required.")

        _logger.debug("UserQuerySet.assign_manager manager_id=%s", manager_id)
        c = self._client

        async for chunked_users in utils.achunks(self.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for i, u in enumerate(chunked_users, start=1):
                request = await u.assign_manager(
                    manager_id, as_batch_request=True, request_id=str(i)
                )
                if request:
                    requests.append(request)

            _logger.debug("UserQuerySet.assign_manager batch size=%s", len(requests))
            batch_resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(
                batch_resp, requests, action="assign manager to users"
            )

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
        Reset passwords for all users in this queryset and export results to CSV.

        Users are processed in Graph `$batch` requests of up to 20 items. A CSV file
        is always written to `path` with one row per processed user, including the
        password used for reset (provided or generated), plus selected identity fields.

        Args:
                path:
                        Destination CSV path for exported reset details. Existing files
                        are overwritten.
                password:
                        Password to apply to every user in this queryset. Required unless
                        `auto_generate_password=True`.
                auto_generate_password:
                        When `True`, generate a random password per user if `password`
                        is not provided.
                force_change_password_next_sign_in:
                        Whether users must change password at next sign-in.
                force_change_password_next_sign_in_with_mfa:
                        Whether users must change password at next sign-in with MFA.

        Returns:
                None

        Raises:
                ValueError:
                        If `password` is missing and `auto_generate_password` is `False`.
                httpx.HTTPStatusError:
                        If Microsoft Graph returns an error for any batch request.

        Notes:
                - Export CSV columns: `password`, `display_name`, `user_principal_name`,
                  `mobile_phone`, `id`.
                - Batch failures are surfaced via `utils.raise_batch_errors(...)`.

        Quick usage:
                ```python
                await client.users.filter(account_enabled=True).reset_password(
                        "password-reset-results.csv",
                        auto_generate_password=True,
                        force_change_password_next_sign_in=True,
                )
                ```
        """

        import csv
        from pathlib import Path

        _logger.debug("UserQuerySet.reset_password path=%s", path)
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
                    request = await u.reset_password(
                        password=password,
                        auto_generate_password=auto_generate_password,
                        force_change_password_next_sign_in=force_change_password_next_sign_in,
                        force_change_password_next_sign_in_with_mfa=force_change_password_next_sign_in_with_mfa,
                        as_batch_request=True,
                        request_id=str(i),
                    )
                    if request:
                        requests.append(request)
                    writer.writerow(
                        {
                            "password": u.get_generated_password(),
                            "display_name": u.display_name,
                            "user_principal_name": u.user_principal_name,
                            "mobile_phone": u.mobile_phone,
                            "id": u.id,
                        }
                    )

                _logger.debug(
                    "UserQuerySet.reset_password batch size=%s", len(requests)
                )
                batch_resp = await self._client.post(
                    "/$batch", body={"requests": requests}
                )
                utils.raise_batch_errors(
                    batch_resp, requests, action="reset user passwords"
                )

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
        licenses: str | Collection[str] | None = None,
        manager: str | None = None,
        **kwargs: Any,
    ) -> "User":
        """
        Create a single Microsoft Graph user.

        This helper builds a `User` object, validates required/create-safe fields,
        sends `POST /users`, then refreshes the model from Graph response data.
        Optional post-create operations are supported:

        1. assign a manager (`manager`)
        2. assign one or more licenses (`licenses`)

        Args:
                display_name: User display name.
                user_principal_name: User principal name (UPN), e.g. `user@contoso.com`.
                mail_nickname: Mail nickname/alias.
                account_enabled: Whether the account is enabled. Defaults to `True`.
                password: Initial password. Required unless `auto_generate_password=True`.
                force_change_password_next_sign_in:
                        Whether user must change password at next sign-in. Defaults to `True`.
                auto_generate_password:
                        Generate a random password when `password` is not provided.
                licenses:
                        Single license or collection of licenses to assign after user creation.
                        Values can be SKU GUIDs or product names resolvable via
                        `SubscribedSku.get_sku_id(...)`.
                manager:
                        Manager object id or resolvable UPN to assign after creation.
                **kwargs:
                        Additional `User` fields supported by the model.

        Returns:
                User: Created `User` model instance populated from Graph data.

        Raises:
                ValueError:
                        If password is missing and auto-generation is disabled; or if any
                        license in `licenses` cannot be resolved.
                httpx.HTTPStatusError:
                        If Graph returns an HTTP error during create/manager/license calls.

        Notes:
                - Generated password (when used) is stored temporarily on the returned
                  user and can be read once via `user.get_generated_password()`.
                - Manager/license assignment happens after the user is created; this
                  method does not roll back user creation if a later step fails.

        Quick usage:
                ```python
                user = await client.users.create(
                        display_name="Adele Vsance",
                        user_principal_name="adele.vance@contoso.com",
                        mail_nickname="adele.vance",
                        auto_generate_password=True,
                )

                print(user.id, user.display_name)
                print(user.get_generated_password())  # one-time read
                ```
        """
        _logger.debug(
            "UserQuerySet.create display_name=%s user_principal_name=%s",
            display_name,
            user_principal_name,
        )

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
        if licenses is not None:
            if isinstance(licenses, (str, bytes)) or not isinstance(
                licenses, Collection
            ):
                licenses = (licenses,)

            resolved: list[str] = []
            for item in licenses:
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

    async def create_many(
        self,
        *args: dict[str, Any],
        auto_generate_password: bool = False,
        force_change_password_next_sign_in: bool = True,
        path: str | Path | None = None,
        encoding: str = "utf-8",
        export_path: str | Path | None = None,
        export_encoding: str = "utf-8",
    ) -> "UserQuerySet":
        """
        Create many users in Graph using `$batch` requests.

        This method accepts user payloads from two sources:

        1. inline dict records via `*args`
        2. CSV rows loaded from `path`

        All items are normalized to model field names, split into chunks of 20,
        and submitted through `POST /$batch`. Returned users are exposed as a
        seeded `UserQuerySet` (via `with_objects(...)`).

        Args:
                *args:
                        Inline user dictionaries. Keys may be snake_case model field names
                        or Graph-style/camelCase names (which are normalized where possible).
                auto_generate_password:
                        Generate a password for each user missing `password`.
                force_change_password_next_sign_in:
                        Sets `passwordProfile.forceChangePasswordNextSignIn` for created users.
                path:
                        Optional CSV file path. Rows are appended to inline `*args`.
                encoding:
                        Encoding used when reading CSV input. Defaults to `utf-8`.
                export_path:
                        Optional output CSV path. When set, created user details plus generated
                        passwords are exported.
                export_encoding:
                        Encoding used for the export CSV. Defaults to `utf-8`.

        Returns:
                UserQuerySet:
                        A queryset seeded with created `User` objects. If no input items are
                        provided, returns an empty seeded queryset.

        Raises:
                ValueError:
                        If CSV `path` does not exist, or when an item lacks `password` and
                        `auto_generate_password` is `False`.
                httpx.HTTPStatusError:
                        If Graph returns an HTTP error for the batch create call.

        Notes:
                - Graph batch requests are sent in groups of at most 20 items.
                - Blank string values are ignored during item normalization.
                - Generated passwords are temporarily attached to user objects and can be
                  exported through `export_path`.

        Quick usage:
                ```python
                created = await client.users.create_many(
                        {
                                "display_name": "User One",
                                "user_principal_name": "user.one@contoso.com",
                                "mail_nickname": "user.one",
                                "password": "Pass@word123!",
                        },
                        {
                                "display_name": "User Two",
                                "user_principal_name": "user.two@contoso.com",
                                "mail_nickname": "user.two",
                                "password": "Pass@word123!",
                        },
                )

                users = [u async for u in created]
                print(len(users))
                ```
        """

        import csv
        from pathlib import Path

        items: list[dict[str, Any]] = list(args)
        if path:
            path = Path(path)
            if not path.exists():
                raise ValueError(f"CSV path does not exist: {path}")
            with path.open("r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    items.append(dict(row))
        if not items:
            return self.with_objects()

        _logger.debug("UserQuerySet.create_many items=%s", len(items))
        created: list[User] = []
        for chunk_items in utils.chunks(items, 20):
            requests: list[dict[str, Any]] = []
            mapping: dict[str, User] = {}

            for i, raw in enumerate(chunk_items, start=1):
                data: dict[str, Any] = {}
                for key, val in raw.items():
                    if val is None:
                        continue
                    if isinstance(val, str) and not val.strip():
                        continue
                    k = key if key in User.FIELDS else utils.to_snake_case(key)
                    data[k] = val

                password = data.pop("password", None)
                if not password and auto_generate_password:
                    password = utils.generate_password(14)
                if not password:
                    raise ValueError(
                        "'password' is required when creating a user. "
                        "Set auto_generate_password=True to generate one."
                    )

                data["password_profile"] = dict(
                    password=password,
                    force_change_password_next_sign_in=force_change_password_next_sign_in,
                )

                obj = User(client=self._client, path=self.path, **data)
                setattr(obj, "__generated_password", password)
                obj._validate_for_create()

                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": self.path,
                        "headers": {"Content-Type": "application/json"},
                        "body": obj.serialize(),
                    }
                )
                mapping[str(i)] = obj

            batch_resp = await self._client.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(batch_resp, requests, action="create users")

            for resp in batch_resp.get("responses", []) or []:
                obj = mapping.get(str(resp.get("id")))
                if obj is None:
                    continue
                body = resp.get("body") or {}
                if body:
                    merged = dict(body)
                    for attr_name, val in obj._data.items():
                        field = obj.FIELDS.get(attr_name)
                        if field is None or field.write_only:
                            continue
                        graph_attr_name = field.graph_attr_name or attr_name
                        merged.setdefault(graph_attr_name, field.to_graph(val))
                    obj.refresh_from_graph(merged)
                created.append(obj)

        qs = self.with_objects(*created)

        if export_path:
            await qs.to_csv(
                export_path,
                fieldnames=(
                    "id",
                    "display_name",
                    "user_principal_name",
                    lambda o: {"password": getattr(o, "__generated_password", None)},
                ),
                encoding=export_encoding,
            )

        return qs

    def disabled_with_assigned_licenses(self) -> Self:
        """
        Filter users that are disabled and still have assigned licenses.

        Returns:
                UserQuerySet:
                        Queryset where `account_enabled=False` and
                        `assigned_licenses__is_null=False`.
        """
        return self.filter(account_enabled=False, assigned_licenses__is_null=False)

    def enabled_with_no_assigned_licenses(self) -> Self:
        """
        Filter users that are enabled and have no assigned licenses.

        Returns:
                UserQuerySet:
                        Queryset where `account_enabled=True` and
                        `assigned_licenses__is_null=True`.
        """
        return self.filter(account_enabled=True, assigned_licenses__is_null=True)
