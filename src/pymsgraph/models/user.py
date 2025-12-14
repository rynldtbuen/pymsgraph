from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pymsgraph.fields import (
    BooleanField,
    CharField,
    EmailField,
)
from pymsgraph.manager import BaseManager
from pymsgraph.models.base import GraphModel
from pymsgraph.queryset import QuerySet
from pymsgraph import utils

if TYPE_CHECKING:
    from pymsgraph.models.group import Group


class UserQuerySet(QuerySet):
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

    def add(self, group_id: str) -> None:
        """Add *this user* to the group (POST /groups/{group-id}/members/$ref)."""
        self.model(id=group_id).members.add(  # type: ignore
            self._kwargs["user"].get_directory_object_id()
        )

    def remove(self, group_id: str) -> None:
        self.model(id=group_id).members.remove(  # type: ignore
            self._kwargs["user"].get_directory_object_id()
        )
