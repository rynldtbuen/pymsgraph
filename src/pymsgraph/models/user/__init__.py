from pymsgraph import utils
from pymsgraph.models.base import Model
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    EmailField,
    ModelField,
    QuerySetField,
)

from .model_fields import PasswordProfile, AssignedLicensesQuerySet

__all__ = ["User"]


class User(Model):
    """
    Graph user resource type.

    https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0
    """

    display_name = CharField(required=True)
    account_enabled = BooleanField(default=True, required=True)
    mail_nickname = CharField(required=True)
    user_principal_name = EmailField(required=True)

    # about_me = CharField()
    # age_group = CharField()
    assigned_licenses = QuerySetField(AssignedLicensesQuerySet)
    # assigned_plans = Field(read_only=True)
    # birthday = DateTimeField()
    # business_phones = Field()
    # city = CharField(max_length=128)
    # company_name = CharField()
    # consent_provided_for_minor = CharField()
    # country = CharField()
    # created_date_time = DateTimeField(read_only=True)
    # creation_type = CharField()
    # custom_security_attributes = Field()
    # department = CharField()
    # employee_hire_date = DateTimeField()
    # employee_id = CharField()
    # employee_org_data = Field()
    # employee_type = CharField()
    # fax_number = CharField()
    # given_name = CharField()
    # hire_date = DateTimeField()
    # identities = Field()
    # im_addresses = Field()
    # job_title = CharField()
    # mail = EmailField(read_only=True)
    # mobile_phone = CharField()
    # interests = Field()
    # office_location = CharField()
    # is_management_restricted = BooleanField()
    # is_resource_account = BooleanField()
    # legal_age_group_classification = CharField()
    # license_assignment_states = Field(read_only=True)
    # last_password_change_date_time = DateTimeField(read_only=True)
    # mailbox_settings = Field(read_only=True)
    # my_site = CharField()
    # on_premises_distinguished_name = CharField()
    # on_premises_domain_name = CharField()
    # on_premises_extension_attributes = Field()
    # on_premises_immutable_id = CharField()
    # on_premises_last_sync_date_time = DateTimeField(read_only=True)
    # on_premises_provisioning_errors = Field(read_only=True)
    # on_premises_sam_account_name = CharField()
    # on_premises_security_identifier = CharField(read_only=True)
    # on_premises_sync_enabled = BooleanField()
    # on_premises_user_principal_name = CharField()
    # other_mails = Field()
    # password_policies = CharField()
    password_profile = ModelField(PasswordProfile)
    # past_projects = Field()
    # postal_code = CharField()
    # preferred_data_location = CharField()
    # preferred_language = CharField()
    # preferred_name = CharField()
    # provisioned_plans = Field(read_only=True)
    # proxy_addresses = Field()
    # responsibilities = Field()
    # schools = Field()
    # security_identifier = CharField(read_only=True)
    # service_provisioning_errors = Field(read_only=True)
    # show_in_address_list = BooleanField()
    # sign_in_activity = Field(read_only=True)
    # sign_in_sessions_valid_from_date_time = DateTimeField(read_only=True)
    # skills = Field()
    # state = CharField()
    # street_address = CharField()
    # surname = CharField()
    # usage_location = CharField()
    # user_type = CharField()

    # Relationship
    # member_of = QuerySetField(query.MemberOfQuerySet)

    # search_field = "display_name"
    # endpoint = "/users"
    # supported_lookup = query.supported_lookup

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

        await self._ctx.client.patch(ep, body=body)

    def revoke_sign_in_sessions(self):
        return self._ctx.client.post(f"{self._endpoint}/revokeSignInSessions")

    def get_generated_password(self) -> str | None:
        """Return the auto-generated password (if any) and clear it immediately."""
        pwd = getattr(self, "_generated_password", None)
        self._generated_password = None
        return pwd

    async def delete(self, *, force: bool = False) -> None:
        if not force:
            raise RuntimeError("Call delete(force=True) to proceed.")

        await self._ctx.client.delete(self._endpoint)

        self._data.clear()
        self._dirty.clear()


# class UserQuerySet(QuerySet["User"]):
#     model_class = User
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

#     def create(
#         self,
#         *,
#         display_name: str,
#         user_principal_name: str,
#         mail_nickname: str,
#         account_enabled: bool = True,
#         password: str | None = None,
#         force_change_password_next_sign_in: bool = True,
#         auto_generate_password: bool = False,
#         **kwargs: Any,
#     ) -> "User":
#         if password is None:
#             if not auto_generate_password:
#                 raise ValueError(
#                     "'password' is required when creasting a user. Set auto_generate_password=True to let the system create a random password for this user."
#                 )
#             password = utils.generate_password(14)

#         obj = self.model_class(
#             display_name=display_name,
#             user_principal_name=user_principal_name,
#             mail_nickname=mail_nickname,
#             account_enabled=account_enabled,
#             parent=self,
#             **kwargs,
#         )
#         obj._validate_for_create()
#         payload = obj.to_graph(for_update=False)
#         payload.update(
#             PasswordProfile(
#                 password=password,
#                 force_change_password_next_sign_in=force_change_password_next_sign_in,
#             ).to_graph()
#         )
#         obj.refresh_from_graph(self._client.post(self.endpoint, json_body=payload))
#         return obj

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
