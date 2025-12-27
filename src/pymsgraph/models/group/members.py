from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, TypeAlias
from pymsgraph import utils
from pymsgraph.query import Capabilities, QuerySet

if TYPE_CHECKING:
    from pymsgraph.models.user import User


arg_types: TypeAlias = "str | User | Iterable[str] | Iterable[User] | QuerySet[User]"


class MembersQuerySet(QuerySet["User"]):
    """
    Group's members queryset.

    Usage:
        Group.members
        Group.members.add(...)
        Group.members.remove(...)
    """

    model_class = "User"  # type: ignore
    endpoint = "/members"
    capabilities = Capabilities.read_only()

    def add(self, *args: arg_types) -> None:
        """
        Add user/s to this group.
        """

        c = self._client
        objects = utils.coerce_objects(*args, queryset=c.users)
        assert self._parent is not None
        for users in utils.chunks(objects, 20):
            binds = [f"{c.base_url}/directoryObjects/{u.id}" for u in users]
            c.patch(
                self._parent.endpoint,
                json_body={"members@odata.bind": binds},
            )

    def remove(self, *args: arg_types) -> None:
        """
        Remove user/s from this group.
        """

        c = self._client
        objects = utils.coerce_objects(*args, queryset=c.users)

        for users in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for index, user in enumerate(users, start=1):
                requests.append(
                    {
                        "id": str(index),
                        "method": "DELETE",
                        "url": f"{self.endpoint}/{user.id}/$ref",
                    }
                )
            resp = c.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="remove user/s from this groups")
