from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any, ClassVar, TypeAlias

from pymsgraph import utils
from pymsgraph.query import BulkQuerySet, Capabilities, QuerySet

if TYPE_CHECKING:
    from pymsgraph.models.group import Group

arg_types: TypeAlias = "str | Group | Iterable[str] | Iterable[Group] | QuerySet[Group]"


class GroupsQuerySet(QuerySet["Group"]):
    """
    User's groups queryset.

    Usage:
        User.groups
        User.groups.add(...)
        User.groups.remove(...)
    """

    model_class = "Group"  # type: ignore

    capabilities = Capabilities.read_only()

    def add(self, *args: arg_types) -> None:
        """
        Add group/s to this user.
        """

        user = self._get_object()
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
                        "method": "POST",
                        "url": f"{group.endpoint}/members/$ref",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "@odata.id": f"{client.base_url}/directoryObjects/{user.id}"
                        },
                    }
                )
            resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="add user to groups")

    def remove(self, *args: arg_types) -> None:
        """
        Remove group/s from this user.
        """

        user = self._get_object()
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

    def _iter_objects(self, data: dict[str, Any]) -> Iterator["Group"]:
        for item in data.get("value", []):
            otype = item.get("@odata.type")
            if otype and otype.lower() != "#microsoft.graph.group":
                continue
            yield self.model_class(graph_data=item, qs=self)


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
