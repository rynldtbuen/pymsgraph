from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pymsgraph import utils
from pymsgraph.fields import BooleanField, CharField, EmailField
from pymsgraph.models.subscribed_sku import ServicePlanInfo

from .base import Model, ReadOnlyModel

if TYPE_CHECKING:
    from pymsgraph.models.group import Group


# class _UserQuerySetGroups(QuerySetBulkOperation):
#     """
#     Bulk operation of user group assignment using batch

#     Usage:
#       - User.objects.filter(...).groups.add/remove(...)
#     """

#     def add(self, *groups: "str | Group | QuerySet['Group']") -> None:
#         """
#         Add users in this queryset to one or many groups.

#         Uses PATCH /groups/{id} with members@odata.bind (up to 20 per PATCH)
#         """
#         group_ids = utils.coerce_values(*groups, attr_names=("id",))
#         if not group_ids:
#             return

#         user_ids = self.get_ids()
#         if not user_ids:
#             return

#         model = self.qs.model
#         client = model._get_client()

#         for gid in group_ids:
#             for chunk in utils.chunks(user_ids, 20):
#                 binds = [f"{client.base_url}/directoryObjects/{uid}" for uid in chunk]
#                 client.patch(
#                     f"{model.endpoint}/{gid}",
#                     json_body={"members@odata.bind": binds},
#                 )

#     def remove(self, *groups: "str | Group | QuerySet['Group']") -> None:
#         """
#         Remove users in this queryset from one or many groups.

#         Uses $batch of DELETE /groups/{id}/members/{user-id}/$ref (20 per batch)
#         """
#         group_ids = utils.coerce_values(*groups, attr_names=("id",))
#         if not group_ids:
#             return

#         user_ids = self.get_ids()
#         if not user_ids:
#             return

#         model = self.qs.model
#         client = model._get_client()

#         for gid in group_ids:
#             for chunk in utils.chunks(user_ids, 20):
#                 requests: list[dict[str, Any]] = []
#                 for i, uid in enumerate(chunk, start=1):
#                     requests.append(
#                         {
#                             "id": str(i),
#                             "method": "DELETE",
#                             "url": f"{model.endpoint}/{gid}/members/{uid}/$ref",
#                         }
#                     )
#                 batch_resp = client.post("/$batch", json_body={"requests": requests})
#                 utils.raise_batch_errors(batch_resp, action="remove users from groups")


# class _UserQuerySetLicenses(QuerySetBulkOperation):
#     """
#     Bulk operation of user license assignment using batch

#     Usage:
#       - User.objects.filter(...).licenses.add/remove(...)
#     """

#     def _assign(
#         self, *, user_id: str, add: list[str], remove: list[str]
#     ) -> dict[str, Any]:
#         # Graph expects:
#         # { addLicenses: [{skuId, disabledPlans: []}], removeLicenses: [skuId] }
#         return {
#             "addLicenses": [{"skuId": sid, "disabledPlans": []} for sid in add],
#             "removeLicenses": remove,
#         }

#     # ---- public API ----

#     def add(self, *licenses: Any) -> None:
#         """
#         Add users in this queryset to one or many licenses.

#         Uses $batch of POST /users/{id}/assignLicense (20 per batch)
#         """
#         sku_ids = utils.coerce_values(*licenses, attr_names=("sku_id",))
#         if not sku_ids:
#             return

#         user_ids = self.get_ids()
#         if not user_ids:
#             return

#         model = self.qs.model
#         client = model._get_client()

#         for chunk in utils.chunks(user_ids, 20):
#             requests: list[dict[str, Any]] = []
#             for i, uid in enumerate(chunk, start=1):
#                 requests.append(
#                     {
#                         "id": str(i),
#                         "method": "POST",
#                         "url": f"{model.endpoint}/{uid}/assignLicense",
#                         "headers": {"Content-Type": "application/json"},
#                         "body": self._assign(user_id=uid, add=sku_ids, remove=[]),
#                     }
#                 )

#             batch_resp = client.post("/$batch", json_body={"requests": requests})
#             utils.raise_batch_errors(batch_resp, action="add licenses")

#     def remove(self, *licenses: Any) -> None:
#         """
#         Remove users in this queryset from one or many licenses.

#         Uses $batch of POST /users/{id}/assignLicense (20 per batch)
#         """

#         sku_ids = utils.coerce_values(*licenses, attr_names=("sku_id",))
#         if not sku_ids:
#             return

#         user_ids = self.get_ids()
#         if not user_ids:
#             return

#         model = self.qs.model
#         client = model._get_client()

#         for chunk in utils.chunks(user_ids, 20):
#             requests: list[dict[str, Any]] = []
#             for i, uid in enumerate(chunk, start=1):
#                 requests.append(
#                     {
#                         "id": str(i),
#                         "method": "POST",
#                         "url": f"{model.endpoint}/{uid}/assignLicense",
#                         "headers": {"Content-Type": "application/json"},
#                         "body": self._assign(user_id=uid, add=[], remove=sku_ids),
#                     }
#                 )

#             batch_resp = client.post("/$batch", json_body={"requests": requests})
#             utils.raise_batch_errors(batch_resp, action="remove licenses")


# class UserQuerySet(QuerySet["User"]):
#     groups = _UserQuerySetGroups.as_descriptor()
#     licenses = _UserQuerySetLicenses.as_descriptor()

#     def create(self, **kwargs: Any) -> "User":
#         password = kwargs.pop("password", None)
#         force_change_password_next_sign_in = kwargs.pop(
#             "force_change_password_next_sign_in", True
#         )
#         auto_generate_password = kwargs.pop("auto_generate_password", False)
#         obj = self.model(**kwargs)
#         obj.save(
#             password=password,
#             force_change_password_next_sign_in=force_change_password_next_sign_in,
#             auto_generate_password=auto_generate_password,
#         )
#         return obj


class User(Model):
    display_name = CharField(required=True)
    user_principal_name = EmailField(required=True)
    account_enabled = BooleanField(default=True)
    mail_nickname = CharField(required=True)
    mail = EmailField(read_only=True)
    given_name = CharField()
    surname = CharField()
    job_title = CharField()
    department = CharField()
    office_location = CharField()
    mobile_phone = CharField()

    @property
    def groups(self): ...

    @property
    def direct_reports(self): ...

    @property
    def licenses(self): ...

    # def save(self) -> bool:
    # self._generated_password: str | None = None

    # if self.id is None:
    #     if auto_generate_password and not password:
    #         password = utils.generate_password(14)
    #         self._generated_password = password

    #     if not password:
    #         raise ValueError(
    #             "'password' is required when creating a user. Set auto_generate_password=True to let the system create a random password for this user."
    #         )

    #     self._validate_for_create()
    #     payload = self.to_graph(for_update=False)
    #     payload.update(
    #         PasswordProfile(
    #             password=password,
    #             force_change_password_next_sign_in=force_change_password_next_sign_in,
    #         ).to_graph()
    #     )
    #     created = self._client.post(self.endpoint, json_body=payload)
    #     hydrated = self.__class__.from_graph(created)
    #     self._data = hydrated._data
    #     self._dirty.clear()
    #     return

    # if self.id is None:
    #     raise ValueError(
    #         "Cannot save User without an id. Create user via client.users.create(...)"
    #     )

    # payload = self.to_graph(for_update=True)
    # if not payload:
    #     return

    # self._client.patch(self.endpoint, json_body=payload)
    # self._dirty.clear()

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


class PasswordProfile(ReadOnlyModel):
    password = CharField()
    force_change_password_next_sign_in = BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = BooleanField()

    def to_graph(self) -> dict[str, Any]:
        return {"passwordProfile": super().to_graph()}


# class _MemberOfQuerySet(QuerySet["Group"]):
#     def __iter__(self):
#         client = self.model._get_client()
#         data = client.get(
#             self.endpoint, params=self._build_params(), headers=self._headers
#         )

#         for item in data.get("value", []):
#             otype = item.get("@odata.type")
#             if otype and otype.lower() != "#microsoft.graph.group":
#                 continue
#             yield self.model.from_graph(item)

#     @property
#     def endpoint(self) -> str:
#         return f"{self._kwargs['user'].get_endpoint()}/memberOf"

#     def add(self, *groups: "str | Group | QuerySet['Group']") -> None:
#         """
#         Add *this user* to one or many groups.

#         Uses Graph batch:
#         PATCH /groups/{id} with members@odata.bind (1 bind per group)
#         Batched with POST /$batch (max 20 requests per batch).
#         """
#         group_ids = utils.coerce_values(*groups, attr_names=("id",))
#         if not group_ids:
#             return

#         user = self._kwargs["user"]
#         user_id = user.get_directory_object_id()
#         client = self.model._get_client()

#         for chunk in utils.chunks(group_ids, 20):
#             requests: list[dict[str, Any]] = []
#             for i, gid in enumerate(chunk, start=1):
#                 requests.append(
#                     {
#                         "id": str(i),
#                         "method": "PATCH",
#                         "url": f"{self.model.endpoint}/{gid}",  # relative, no /v1.0
#                         "headers": {"Content-Type": "application/json"},
#                         "body": {
#                             "members@odata.bind": [
#                                 f"{client.base_url}/directoryObjects/{user_id}"
#                             ]
#                         },
#                     }
#                 )

#             batch_resp = client.post("/$batch", json_body={"requests": requests})
#             utils.raise_batch_errors(batch_resp, action="add memberOf")

#     def remove(self, *groups: "str | Group | QuerySet['Group']") -> None:
#         """
#         Remove *this user* from one or many groups.

#         Uses:
#         DELETE /groups/{id}/members/{user-id}/$ref
#         Batched with POST /$batch (max 20 requests per batch).
#         """
#         group_ids = utils.coerce_values(*groups, attr_names=("id",))
#         if not group_ids:
#             return

#         user = self._kwargs["user"]
#         user_id = user.get_directory_object_id()
#         client = self.model._get_client()

#         for chunk in utils.chunks(group_ids, 20):
#             requests: list[dict[str, Any]] = []
#             for i, gid in enumerate(chunk, start=1):
#                 requests.append(
#                     {
#                         "id": str(i),
#                         "method": "DELETE",
#                         "url": f"{self.model.endpoint}/{gid}/members/{user_id}/$ref",  # relative
#                     }
#                 )

#             batch_resp = client.post("/$batch", json_body={"requests": requests})
#             utils.raise_batch_errors(batch_resp, action="remove memberOf")


# class LicenseDetails(GraphModel):
#     is_standalone = True

#     service_plans = ServicePlanInfo.as_descriptor()
#     sku_id = CharField()
#     sku_part_number = CharField()


# class _LicensesfQuerySet(BaseQuerySet["LicenseDetails"]):
#     @property
#     def endpoint(self) -> str:
#         return f"{self._kwargs['user'].get_endpoint()}/assignLicense"
