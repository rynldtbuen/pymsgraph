from typing import Any, TYPE_CHECKING

from .fields import BooleanField, CharField, DateTimeField
from .resources import MultiValuedResource, Resource, SingleValuedResource
from .drives import Drive, RootDriveItem

if TYPE_CHECKING:
    from .groups import Group


# https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0&tabs=http
class Users(MultiValuedResource["User"]):

    class RequestQueryParam(MultiValuedResource.RequestQueryParam):
        TOP = True
        SEARCH = True
        COUNT = True

    ITEM_CLASS = "User"

    @property
    def relative_url(self):
        return "/users"

    def by_id(self, user_id: str) -> "User":
        return User(self._client, parent=self, user_id=user_id)

    @classmethod
    def create(
        cls,
        display_name,
        mail_nick_name,
        user_pricipal_name,
        password_profile,
        account_enabled,
        **kwargs,
    ):
        return


class DefaultDrive(Drive):
    @property
    def relative_url(self) -> str:
        return "/drive"

    @property
    def root(self) -> "RootDriveItem":
        return RootDriveItem(self._client, parent=self)


class User(SingleValuedResource):

    class RequestMethod(SingleValuedResource.RequestMethod):
        PATCH = True
        DELETE = True

    id = CharField()
    display_name = CharField()
    user_principal_name = CharField()
    mail = CharField()
    account_enabled = BooleanField()

    @property
    def relative_url(self) -> str:
        return f"/{self._user_id}"

    @property
    def member_of(self) -> "MemberOf":
        return MemberOf(self._client, parent=self)

    @property
    def drive(self) -> "DefaultDrive":
        return DefaultDrive(self._client, parent=self)

    @property
    def revoke_sign_in_sessions(self) -> "RevokeSignInSessions":
        return RevokeSignInSessions(self._client, parent=self)

    @property
    def app_role_assignments(self) -> "AppRoleAssignments":
        return AppRoleAssignments(self._client, parent=self)

    def reset_password(
        self, password: str, force_change_password_next_sign_in: bool = True
    ) -> "User":
        data = {
            "passwordProfile": {
                "forceChangePasswordNextSignIn": force_change_password_next_sign_in,
                "password": password,
            }
        }
        self.patch(data)
        return self

    def sign_out_to_all_sessions(self) -> "User":
        self.revoke_sign_in_sessions.post()
        return self

    def block_sign_in(self):
        pass

    def allow_sign_in(self):
        pass

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        user_id = kwargs.get("user_id") or self.id
        if user_id is None:
            raise ValueError("Parameter is required, 'user_id'")
        self._user_id = user_id


class MemberOf(MultiValuedResource["Group"]):

    ITEM_CLASS = "Group"

    @property
    def relative_url(self):
        return f"/memberOf"


class RevokeSignInSessions(Resource):
    class RequestMethod(Resource.RequestMethod):
        POST = True

    @property
    def relative_url(self):
        return "/revokeSignInSessions"


class AppRoleAssignments(MultiValuedResource["AppRoleAssignment"]):
    ITEM_CLASS = "AppRoleAssignment"

    @property
    def relative_url(self):
        return "/appRoleAssignments"


class AppRoleAssignment(SingleValuedResource):
    id = CharField()
    deletedDateTime = DateTimeField()
    app_role_id = CharField()
    createdDateTime = DateTimeField()
    principal_display_name = CharField()

    @property
    def relative_url(self):
        return "/appRoleAssignments"
