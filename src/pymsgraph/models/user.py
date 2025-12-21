from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Iterator

from pymsgraph import utils
from pymsgraph.fields import BooleanField, CharField, EmailField
from pymsgraph.models.subscribed_sku import ServicePlanInfo
from pymsgraph.query import Q, BulkQuerySet, Capabilities, QuerySet

from .base import Model, ReadOnlyModel

if TYPE_CHECKING:
    from .group import Group


class UserGroupsQuerySet(QuerySet["Group"]):
    # model/endpoint provided when instantiated by descriptor
    capabilities: ClassVar[Capabilities] = Capabilities.read_only()

    @classmethod
    def as_descriptor(cls) -> property:
        def fget(obj: "User", objtype=None) -> UserGroupsQuerySet:
            if obj is None:
                return cls  # type: ignore
            if obj.id is None:
                raise ValueError("User is not initialized or does not exist")
            from .group import Group  # lazy import to avoid cycles

            qs = UserGroupsQuerySet(
                client=obj.client,
                model=Group,
                endpoint=f"{obj.endpoint}/memberOf",
            )
            qs._user_id = obj.id  # type: ignore[attr-defined]
            return qs

        return property(fget=fget)

    def _iter_objects(self, data: dict[str, Any]) -> Iterator[Group]:
        for item in data.get("value", []):
            otype = item.get("@odata.type")
            if otype and otype.lower() != "#microsoft.graph.group":
                continue
            yield self._model(graph_data=item, qs=self)

    def add(self, *groups: Any) -> None:
        """
        Add this user to one or more groups.
        """
        user_id = getattr(self, "_user_id", None)
        if not user_id:
            raise ValueError("User id is not configured for this queryset")

        group_ids = utils.coerce_values(*groups, attr_names=("id",))
        if not group_ids:
            return

        client = self._client
        for chunk in utils.chunks(group_ids, 20):
            requests: list[dict[str, Any]] = []
            for idx, gid in enumerate(chunk, start=1):
                requests.append(
                    {
                        "id": str(idx),
                        "method": "PATCH",
                        "url": f"/groups/{gid}",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "members@odata.bind": [
                                f"{client.base_url}/directoryObjects/{user_id}"
                            ]
                        },
                    }
                )
            resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="add user to groups")

    def remove(self, *groups: Any) -> None:
        """
        Remove this user from one or more groups.
        """
        user_id = getattr(self, "_user_id", None)
        if not user_id:
            raise ValueError("User id is not configured for this queryset")

        group_ids = utils.coerce_values(*groups, attr_names=("id",))
        if not group_ids:
            return

        client = self._client
        for chunk in utils.chunks(group_ids, 20):
            requests: list[dict[str, Any]] = []
            for idx, gid in enumerate(chunk, start=1):
                requests.append(
                    {
                        "id": str(idx),
                        "method": "DELETE",
                        "url": f"/groups/{gid}/members/{user_id}/$ref",
                    }
                )
            resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="remove user from groups")


class LicenseDetails(Model):
    capabilities: ClassVar[Capabilities] = Capabilities.read_only()

    sku_id = CharField(read_only=True)
    sku_part_number = CharField(read_only=True)
    service_plans = ServicePlanInfo.as_descriptor()


class UserLicensesQuerySet(QuerySet[LicenseDetails]):
    capabilities: ClassVar[Capabilities] = Capabilities.read_only()

    @classmethod
    def as_descriptor(cls) -> property:
        def fget(obj: "User", objtype=None) -> UserLicensesQuerySet:
            if obj is None:
                return cls  # type: ignore
            if obj.id is None:
                raise ValueError("User is not initialized or does not exist")
            qs = UserLicensesQuerySet(
                client=obj.client,
                model=LicenseDetails,
                endpoint=f"{obj.endpoint}/licenseDetails",
            )
            qs._user = obj  # type: ignore[attr-defined]
            return qs

        return property(fget=fget)

    def _iter_objects(self, data: dict[str, Any]) -> Iterator[LicenseDetails]:
        for item in data.get("value", []):
            yield self._model(graph_data=item, qs=self)

    def _assign_payload(self, *, add: list[str], remove: list[str]) -> dict[str, Any]:
        return {
            "addLicenses": [{"skuId": sid, "disabledPlans": []} for sid in add],
            "removeLicenses": remove,
        }

    def add(self, *licenses: Any) -> None:
        user = getattr(self, "_user", None)
        if not user:
            raise ValueError("User is not configured for this queryset")

        sku_ids = utils.coerce_values(*licenses, attr_names=("sku_id", "id"))
        if not sku_ids:
            return

        client = self._client
        resp = client.post(
            "/$batch",
            json_body={
                "requests": [
                    {
                        "id": "1",
                        "method": "POST",
                        "url": f"{user.endpoint}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": self._assign_payload(add=sku_ids, remove=[]),
                    }
                ]
            },
        )
        utils.raise_batch_errors(resp, action="add licenses")

    def remove(self, *licenses: Any) -> None:
        user = getattr(self, "_user", None)
        if not user:
            raise ValueError("User is not configured for this queryset")

        sku_ids = utils.coerce_values(*licenses, attr_names=("sku_id", "id"))
        if not sku_ids:
            return

        client = self._client
        resp = client.post(
            "/$batch",
            json_body={
                "requests": [
                    {
                        "id": "1",
                        "method": "POST",
                        "url": f"{user.endpoint}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": self._assign_payload(add=[], remove=sku_ids),
                    }
                ]
            },
        )
        utils.raise_batch_errors(resp, action="remove licenses")


class User(Model):
    display_name = CharField(
        required=True,
        supported_lookups={"exact", "ne", "gte", "lte", "in", "startswith", "isnull"},
    )
    user_principal_name = EmailField(
        required=True,
        supported_lookups={"exact", "ne", "gte", "lte", "in", "startswith", "isnull"},
    )
    account_enabled = BooleanField(default=True)
    mail_nickname = CharField(required=True)
    mail = EmailField(read_only=True)
    given_name = CharField()
    surname = CharField()
    job_title = CharField()
    department = CharField()
    office_location = CharField()
    mobile_phone = CharField()

    search_field = "display_name"

    groups = UserGroupsQuerySet.as_descriptor()
    licenses = UserLicensesQuerySet.as_descriptor()

    @property
    def direct_reports(self): ...

    def save(self) -> bool:
        if self.id is None:
            raise ValueError("User is not initialized or does not exist")

        payload = self.to_graph(for_update=True)
        if not payload:
            return False

        self.client.patch(self.endpoint, json_body=payload)
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

        self.client.patch(self.endpoint, json_body=body)

    def revoke_sign_in_sessions(self):
        return self.client.post(f"{self.endpoint}/revokeSignInSessions")

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

        self.client.delete(self.endpoint)

        # Local cleanup (object represents a deleted remote resource)
        self._data.clear()
        self._dirty.clear()


class PasswordProfile(ReadOnlyModel):
    password = CharField(read_only=True)
    force_change_password_next_sign_in = BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = BooleanField(read_only=True)

    def to_graph(self) -> dict[str, Any]:
        return {"passwordProfile": super().to_graph()}


class BulkUserGroupsQuerySet(BulkQuerySet): ...


class BulkUserLicensesQuerySet(BulkQuerySet): ...


class UserQuerySet(QuerySet[User]):
    model: type[User] = User
    endpoint: str = "/users"
    capabilities: ClassVar[Capabilities] = Capabilities.read_write()

    groups = BulkUserGroupsQuerySet.as_descriptor()

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

        obj = self._model(
            display_name=display_name,
            user_principal_name=user_principal_name,
            mail_nickname=mail_nickname,
            account_enabled=account_enabled,
            qs=self,
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
        c = self._client
        e = self._endpoint
        obj.refresh_from_graph(c.post(e, json_body=payload))
        return obj
