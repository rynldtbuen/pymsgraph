from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any, ClassVar, TypeAlias

from pymsgraph import utils
from pymsgraph.query import BulkQuerySet, Capabilities, QuerySet

if TYPE_CHECKING:
    from pymsgraph.models.group import Group
    from pymsgraph.models.user import User

arg_types: TypeAlias = "str | Group | Iterable[str] | Iterable[Group] | QuerySet[Group]"


class GroupsQuerySet(QuerySet["Group"]):
    """
    User's groups queryset.

    Usage:
        User.groups
        User.groups.add(...)
        User.groups.remove(...)
    """

    capabilities: ClassVar[Capabilities] = Capabilities.read_only()

    @classmethod
    def as_descriptor(cls) -> property:
        def fget(obj: "User", objtype=None) -> GroupsQuerySet:
            if obj is None:
                return cls  # type: ignore
            if obj.id is None:
                raise ValueError("User is not initialized or does not exist")
            # from ..group import Group  # lazy import to avoid cycles

            qs = GroupsQuerySet(
                client=obj.client,
                model="Group",
                endpoint=f"{obj.endpoint}/memberOf",
            )
            qs._user = obj  # type: ignore[attr-defined]
            return qs

        return property(fget=fget)

    def _iter_objects(self, data: dict[str, Any]) -> Iterator["Group"]:
        for item in data.get("value", []):
            otype = item.get("@odata.type")
            if otype and otype.lower() != "#microsoft.graph.group":
                continue
            yield self._model(graph_data=item, qs=self)

    def add(self, *args: arg_types) -> None:
        """
        Add group/s to this user.
        """

        user = getattr(self, "_user", None)
        if not user:
            raise ValueError("User id is not configured for this queryset")

        objects: tuple["Group", ...] = tuple(utils.coerce_objects(*args, model="Group"))
        if not objects:
            return

        client = self._client
        for groups in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for index, group in enumerate(groups, start=1):
                requests.append(
                    {
                        "id": str(index),
                        "method": "PATCH",
                        "url": group.endpoint,
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "members@odata.bind": [
                                f"{client.base_url}/directoryObjects/{user.id}"
                            ]
                        },
                    }
                )
            resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="add user to groups")

    def remove(self, *args: arg_types) -> None:
        """
        Remove group/s from this user.
        """

        user = getattr(self, "_user", None)
        if not user:
            raise ValueError("User id is not configured for this queryset")

        objects: tuple["Group", ...] = tuple(utils.coerce_objects(*args, model="Group"))
        if not objects:
            return

        client = self._client
        for groups in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for index, group in enumerate(groups, start=1):
                requests.append(
                    {
                        "id": str(index),
                        "method": "DELETE",
                        "url": f"{group.endpoint}/members/{user.id}/$ref",
                    }
                )
            resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="remove user from groups")


class GroupsBulkQuerySet(BulkQuerySet):
    """
    User queryset's groups.

    Usage:
        UserQuerySet.filter(...).groups.add(...)
        UserQuerySet.filter(...).groups.remove(...)
    """

    def add(self, *args: arg_types) -> None:
        """
        Add group/s to users in this queryset.
        """

        objects: tuple["Group", ...] = tuple(utils.coerce_objects(*args, model="Group"))
        if not objects:
            return

        client = self._client

        for group in objects:
            for users in utils.chunks(self._qs.select("id"), 20):
                binds = [f"{client.base_url}/directoryObjects/{u.id}" for u in users]
                client.patch(
                    group.endpoint,
                    json_body={"members@odata.bind": binds},
                )

    def remove(self, *args: arg_types) -> None:
        """
        Remove group/s from users in this queryset.
        """
        objects: tuple["Group", ...] = tuple(utils.coerce_objects(*args, model="Group"))
        if not objects:
            return

        client = self._client

        for group in objects:
            for users in utils.chunks(self._qs.select("id"), 20):
                requests: list[dict[str, Any]] = []
                for index, user in enumerate(users, start=1):
                    requests.append(
                        {
                            "id": str(index),
                            "method": "DELETE",
                            "url": f"{group.endpoint}/members/{user.id}/$ref",
                        }
                    )
                batch_resp = client.post("/$batch", json_body={"requests": requests})
                utils.raise_batch_errors(
                    batch_resp, action="remove users in queryset from groups"
                )
