from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pymsgraph import utils
from pymsgraph.fields import BooleanField, CharField, EmailField
from pymsgraph.manager import BaseManager
from pymsgraph.models.base import GraphModel
from pymsgraph.models.subscribed_sku import ServicePlanInfo
from pymsgraph.queryset import QuerySet, QuerySetBulkOperation, BaseQuerySet

if TYPE_CHECKING:
    from pymsgraph.models.group import Group


class _UserQuerySetGroups(QuerySetBulkOperation):
    """
    Bulk operation of user group assignment using batch

    Usage:
      - User.objects.filter(...).groups.add/remove(...)
    """

    def add(self, *groups: "str | Group | QuerySet['Group']") -> None:
        """
        Add users in this queryset to one or many groups.

        Uses PATCH /groups/{id} with members@odata.bind (up to 20 per PATCH)
        """
        group_ids = utils.coerce_values(*groups, attr_names=("id",))
        if not group_ids:
            return

        user_ids = self.get_ids()
        if not user_ids:
            return

        model = self.qs.model
        client = model._get_client()

        for gid in group_ids:
            for chunk in utils.chunks(user_ids, 20):
                binds = [f"{client.base_url}/directoryObjects/{uid}" for uid in chunk]
                client.patch(
                    f"{model.endpoint}/{gid}",
                    json_body={"members@odata.bind": binds},
                )

    def remove(self, *groups: "str | Group | QuerySet['Group']") -> None:
        """
        Remove users in this queryset from one or many groups.

        Uses $batch of DELETE /groups/{id}/members/{user-id}/$ref (20 per batch)
        """
        group_ids = utils.coerce_values(*groups, attr_names=("id",))
        if not group_ids:
            return

        user_ids = self.get_ids()
        if not user_ids:
            return

        model = self.qs.model
        client = model._get_client()

        for gid in group_ids:
            for chunk in utils.chunks(user_ids, 20):
                requests: list[dict[str, Any]] = []
                for i, uid in enumerate(chunk, start=1):
                    requests.append(
                        {
                            "id": str(i),
                            "method": "DELETE",
                            "url": f"{model.endpoint}/{gid}/members/{uid}/$ref",
                        }
                    )
                batch_resp = client.post("/$batch", json_body={"requests": requests})
                utils.raise_batch_errors(batch_resp, action="remove users from groups")


class _UserQuerySetLicenses(QuerySetBulkOperation):
    """
    Bulk operation of user license assignment using batch

    Usage:
      - User.objects.filter(...).licenses.add/remove(...)
    """

    def _assign(
        self, *, user_id: str, add: list[str], remove: list[str]
    ) -> dict[str, Any]:
        # Graph expects:
        # { addLicenses: [{skuId, disabledPlans: []}], removeLicenses: [skuId] }
        return {
            "addLicenses": [{"skuId": sid, "disabledPlans": []} for sid in add],
            "removeLicenses": remove,
        }

    # ---- public API ----

    def add(self, *licenses: Any) -> None:
        """
        Add users in this queryset to one or many licenses.

        Uses $batch of POST /users/{id}/assignLicense (20 per batch)
        """
        sku_ids = utils.coerce_values(*licenses, attr_names=("sku_id",))
        if not sku_ids:
            return

        user_ids = self.get_ids()
        if not user_ids:
            return

        model = self.qs.model
        client = model._get_client()

        for chunk in utils.chunks(user_ids, 20):
            requests: list[dict[str, Any]] = []
            for i, uid in enumerate(chunk, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{model.endpoint}/{uid}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": self._assign(user_id=uid, add=sku_ids, remove=[]),
                    }
                )

            batch_resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="add licenses")

    def remove(self, *licenses: Any) -> None:
        """
        Remove users in this queryset from one or many licenses.

        Uses $batch of POST /users/{id}/assignLicense (20 per batch)
        """

        sku_ids = utils.coerce_values(*licenses, attr_names=("sku_id",))
        if not sku_ids:
            return

        user_ids = self.get_ids()
        if not user_ids:
            return

        model = self.qs.model
        client = model._get_client()

        for chunk in utils.chunks(user_ids, 20):
            requests: list[dict[str, Any]] = []
            for i, uid in enumerate(chunk, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{model.endpoint}/{uid}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": self._assign(user_id=uid, add=[], remove=sku_ids),
                    }
                )

            batch_resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="remove licenses")


class UserQuerySet(QuerySet["User"]):
    groups = _UserQuerySetGroups.as_descriptor()
    licenses = _UserQuerySetLicenses.as_descriptor()

    def create(self, **kwargs: Any) -> "User":
        password = kwargs.pop("password", None)
        force_change_password_next_sign_in = kwargs.pop(
            "force_change_password_next_sign_in", True
        )
        auto_generate_password = kwargs.pop("auto_generate_password", False)
        obj = self.model(**kwargs)
        obj.save(
            password=password,
            force_change_password_next_sign_in=force_change_password_next_sign_in,
            auto_generate_password=auto_generate_password,
        )
        return obj


class User(GraphModel):
    endpoint = "/users"

    objects = UserQuerySet.as_manager()

    display_name = CharField(required=True, max_length=100, strip=True)
    user_principal_name = EmailField(required=True, max_length=50, strip=True)
    account_enabled = BooleanField(default=True)

    mail_nickname = CharField(
        required=True, max_length=64
    )  # mailNickname :contentReference[oaicite:5]{index=5}

    @property
    def groups(self):
        try:
            return self._groups  # type: ignore
        except AttributeError:
            from .group import Group

            groups = BaseManager.from_queryset(_MemberOfQuerySet)(Group, user=self)
            self._groups = groups
            return groups

    @property
    def direct_reports(self):
        try:
            return self._direct_reports  # type: ignore
        except AttributeError:
            # TODO: implement DirectReportsQuerySet(User, user=self)
            raise NotImplementedError("direct_reports is not implemented yet")

    def save(
        self,
        password: str | None = None,
        force_change_password_next_sign_in: bool = True,
        auto_generate_password: bool = False,
    ) -> None:
        client = self.__class__._get_client()

        self._generated_password: str | None = None

        if self.id is None:
            if auto_generate_password and not password:
                password = utils.generate_password(14)
                self._generated_password = password

            if not password:
                raise ValueError(
                    "'password' is required when creating a user. Set auto_generate_password=True to let the system create a random password for this user."
                )

            self._validate_for_create()
            payload = self.to_graph(for_update=False)
            payload.update(
                PasswordProfile(password, force_change_password_next_sign_in).to_graph()
            )
            created = client.post(self.endpoint, json_body=payload)
            hydrated = self.__class__.from_graph(created)
            self._data = hydrated._data
            self._dirty.clear()
            return

        payload = self.to_graph(for_update=True)
        if not payload:
            return

        client.patch(f"{self.endpoint}/{self.id}", json_body=payload)
        self._dirty.clear()

    def reset_password(
        self,
        *,
        password: str | None = None,
        force_change_password_next_sign_in: bool = True,
        force_change_password_next_sign_in_with_mfa: bool | None = None,
        auto_generate_password: bool = False,
    ) -> None:
        """Reset this user's password (admin reset) via PATCH /users/{id}.

        - If auto_generate_password=True and password is not provided, generates a
          strong random password and stores it temporarily. Retrieve it once with
          get_generated_password().
        - Graph will never return the password again.
        """
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

        client = self.__class__._get_client()
        body = PasswordProfile(
            password=password,
            force_change_password_next_sign_in=force_change_password_next_sign_in,
            force_change_password_next_sign_in_with_mfa=force_change_password_next_sign_in_with_mfa,
        ).to_graph()

        client.patch(f"{self.endpoint}/{self.id}", json_body=body)

    def revoke_sign_in_sessions(self):
        return self.__class__._get_client().post(
            f"{self.get_endpoint()}/revokeSignInSessions"
        )

    def delete(self, *, force: bool = False) -> None:
        """Delete this user via DELETE /users/{id}.

        Safety:
            Requires force=True to proceed.

        This mirrors a confirmation prompt in non-interactive library code.
        Callers (CLI/UI) can catch the exception and ask the user to confirm.
        """
        # if self.id is None:
        #     raise ValueError("Cannot delete an unsaved User (missing id)")

        if not force:
            raise RuntimeError(
                "Refusing to delete User without confirmation. "
                "Call delete(force=True) to proceed."
            )

        client = self.__class__._get_client()
        client.delete(f"{self.endpoint}/{self.get_id()}")

        # Local cleanup (object represents a deleted remote resource)
        self._data.clear()
        self._dirty.clear()

    def get_generated_password(self) -> str | None:
        """Return the auto-generated password (if any) and clear it immediately.

        This is ONLY available in-memory right after creation. Graph will never return it.
        """
        pwd = getattr(self, "_generated_password", None)
        self._generated_password = None
        return pwd

    def get_id(self):
        val = self.id or self.user_principal_name
        if not val:
            raise ValueError("model is not initialized or does not exist.")
        return val

    def get_directory_object_id(self) -> str:
        if self.id:
            return self.id

        client = self.__class__._get_client()
        payload = client.get(self.get_endpoint())
        self.refresh_from_graph(payload)
        if not self.id:
            raise RuntimeError("Graph did not return an id for this user")
        return self.id


@dataclass(frozen=True, slots=True)
class PasswordProfile:
    password: str
    force_change_password_next_sign_in: bool = True
    force_change_password_next_sign_in_with_mfa: bool | None = None

    def to_graph(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "password": self.password,
            "forceChangePasswordNextSignIn": self.force_change_password_next_sign_in,
        }
        if self.force_change_password_next_sign_in_with_mfa is not None:
            out["forceChangePasswordNextSignInWithMfa"] = (
                self.force_change_password_next_sign_in_with_mfa
            )
        return {"passwordProfile": out}


class _MemberOfQuerySet(QuerySet["Group"]):
    def __iter__(self):
        client = self.model._get_client()
        data = client.get(
            self.endpoint, params=self._build_params(), headers=self._headers
        )

        for item in data.get("value", []):
            otype = item.get("@odata.type")
            if otype and otype.lower() != "#microsoft.graph.group":
                continue
            yield self.model.from_graph(item)

    @property
    def endpoint(self) -> str:
        return f"{self._kwargs['user'].get_endpoint()}/memberOf"

    def add(self, *groups: "str | Group | QuerySet['Group']") -> None:
        """
        Add *this user* to one or many groups.

        Uses Graph batch:
        PATCH /groups/{id} with members@odata.bind (1 bind per group)
        Batched with POST /$batch (max 20 requests per batch).
        """
        group_ids = utils.coerce_values(*groups, attr_names=("id",))
        if not group_ids:
            return

        user = self._kwargs["user"]
        user_id = user.get_directory_object_id()
        client = self.model._get_client()

        for chunk in utils.chunks(group_ids, 20):
            requests: list[dict[str, Any]] = []
            for i, gid in enumerate(chunk, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "PATCH",
                        "url": f"{self.model.endpoint}/{gid}",  # relative, no /v1.0
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "members@odata.bind": [
                                f"{client.base_url}/directoryObjects/{user_id}"
                            ]
                        },
                    }
                )

            batch_resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="add memberOf")

    def remove(self, *groups: "str | Group | QuerySet['Group']") -> None:
        """
        Remove *this user* from one or many groups.

        Uses:
        DELETE /groups/{id}/members/{user-id}/$ref
        Batched with POST /$batch (max 20 requests per batch).
        """
        group_ids = utils.coerce_values(*groups, attr_names=("id",))
        if not group_ids:
            return

        user = self._kwargs["user"]
        user_id = user.get_directory_object_id()
        client = self.model._get_client()

        for chunk in utils.chunks(group_ids, 20):
            requests: list[dict[str, Any]] = []
            for i, gid in enumerate(chunk, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "DELETE",
                        "url": f"{self.model.endpoint}/{gid}/members/{user_id}/$ref",  # relative
                    }
                )

            batch_resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="remove memberOf")


class LicenseDetails(GraphModel):
    is_standalone = True

    service_plans = ServicePlanInfo.as_descriptor()
    sku_id = CharField()
    sku_part_number = CharField()


class _LicensesfQuerySet(BaseQuerySet["LicenseDetails"]):
    @property
    def endpoint(self) -> str:
        return f"{self._kwargs['user'].get_endpoint()}/assignLicense"
