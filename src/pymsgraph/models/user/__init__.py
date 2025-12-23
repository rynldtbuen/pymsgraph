from __future__ import annotations

from typing import Any, ClassVar

from pymsgraph import utils
from pymsgraph.fields import BooleanField, CharField, EmailField
from pymsgraph.models.user import compile_lookup
from pymsgraph.models.user.groups import GroupsBulkQuerySet, GroupsQuerySet
from pymsgraph.models.user.licenses import LicensesQuerySet
from pymsgraph.query import Capabilities, QuerySet

from ..base import EndpointDescriptor, Model

__all__ = ["UserQuerySet"]


class User(Model):
    """
    Graph user resource type.

    https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0
    """

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
    city = CharField(max_length=128, supported_lookups={"exact", "in", "startswith"})

    search_field = "display_name"
    endpoint = EndpointDescriptor("/users")

    groups = GroupsQuerySet.as_descriptor()
    licenses = LicensesQuerySet.as_descriptor()

    @property
    def direct_reports(self): ...

    def __repr__(self):
        return f"<User: {self.display_name}>"

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


class UserQuerySet(QuerySet["User"]):
    model: type[User] = User
    capabilities: ClassVar[Capabilities] = Capabilities.read_write(search=True)
    related_lookup = {"licenses": compile_lookup._licenses}

    groups: GroupsBulkQuerySet = GroupsBulkQuerySet.as_descriptor(endpoint="/groups")  # type: ignore

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


class PasswordProfile(Model):
    is_read_only = True
    password = CharField(read_only=True)
    force_change_password_next_sign_in = BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = BooleanField(read_only=True)

    def to_graph(self, *, for_update: bool = False) -> dict[str, Any]:
        return {"passwordProfile": super().to_graph(for_update=False)}
