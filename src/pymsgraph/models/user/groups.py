from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any, TypeAlias

from pymsgraph import utils
from pymsgraph.query import BulkQuerySet, Capabilities, QuerySet

if TYPE_CHECKING:
    from pymsgraph.models.user import User
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
    endpoint = "/memberOf"
    capabilities = Capabilities.read_only()

    def add(self, *args: arg_types) -> None:
        """
        Add group/s to this user.
        """

        c = self._client
        u: "User" = getattr(self, "_parent")
        objects = utils.coerce_objects(*args, queryset=c.groups)

        for groups in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for i, g in enumerate(groups, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{g.members.endpoint}/$ref",
                        "headers": {"Content-Type": "application/json"},
                        "body": {"@odata.id": f"{c.base_url}/directoryObjects/{u.id}"},
                    }
                )
            resp = c.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="add user to groups")

    def remove(self, *args: arg_types) -> None:
        """
        Remove group/s from this user.
        """

        c = self._client
        u: User = getattr(self, "_parent")
        objects = utils.coerce_objects(*args, queryset=c.groups)

        for groups in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for i, g in enumerate(groups, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "DELETE",
                        "url": f"{g.members.endpoint}/{u.id}/$ref",
                    }
                )
            resp = c.post("/$batch", json_body={"requests": requests})
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

        c = self._client
        objects = utils.coerce_objects(*args, queryset=c.groups)

        for group in objects:
            for users in utils.chunks(self._queryset.select("id"), 20):
                binds = [f"{c.base_url}/directoryObjects/{u.id}" for u in users]
                c.patch(
                    group.endpoint,
                    json_body={"members@odata.bind": binds},
                )

    def remove(self, *args: arg_types) -> None:
        """
        Remove group/s from users in this queryset.
        """
        c = self._client
        objects = utils.coerce_objects(*args, queryset=c.groups)

        for group in objects:
            for users in utils.chunks(self._queryset.select("id"), 20):
                requests: list[dict[str, Any]] = []
                for i, u in enumerate(users, start=1):
                    requests.append(
                        {
                            "id": str(i),
                            "method": "DELETE",
                            "url": f"{group.members.endpoint}/{u.id}/$ref",
                        }
                    )
                batch_resp = c.post("/$batch", json_body={"requests": requests})
                utils.raise_batch_errors(
                    batch_resp, action="remove users in queryset from groups"
                )
