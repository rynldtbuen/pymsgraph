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
    capabilities = Capabilities.read_only()

    def add(self, *args: arg_types) -> None:
        """
        Add user/s to this group members.
        """

        group = getattr(self, "_obj", None)
        if not group:
            raise ValueError("No Group object found.")

        objects: tuple["User", ...] = tuple(utils.coerce_objects(*args, model="Group"))
        if not objects:
            return

        client = self._client
        for users in utils.chunks(objects, 20):
            binds = [f"{client.base_url}/directoryObjects/{u.id}" for u in users]
            client.patch(
                group.endpoint,
                json_body={"members@odata.bind": binds},
            )

    def remove(self, *args: arg_types) -> None:
        """
        Remove user/s to this group members.
        """

        group = getattr(self, "_obj", None)
        if not group:
            raise ValueError("No Group object found.")

        objects: tuple["User", ...] = tuple(utils.coerce_objects(*args, model="Group"))
        if not objects:
            return

        client = self._client
        for users in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for index, user in enumerate(users, start=1):
                requests.append(
                    {
                        "id": str(index),
                        "method": "DELETE",
                        "url": f"{group.endpoint}/members/{user.id}/$ref",
                    }
                )
            resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="remove user/s from this groups")
