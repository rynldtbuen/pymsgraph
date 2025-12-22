from typing import TYPE_CHECKING, Any, ClassVar, Iterator

from pymsgraph import utils
from pymsgraph.query import Capabilities, QuerySet

if TYPE_CHECKING:
    from pymsgraph.models.group import Group
    from pymsgraph.models.user import User


class UserGroupsQuerySet(QuerySet["Group"]):
    capabilities: ClassVar[Capabilities] = Capabilities.read_only()

    @classmethod
    def as_descriptor(cls) -> property:
        def fget(obj: "User", objtype=None) -> UserGroupsQuerySet:
            if obj is None:
                return cls  # type: ignore
            if obj.id is None:
                raise ValueError("User is not initialized or does not exist")
            from ..group import Group  # lazy import to avoid cycles

            qs = UserGroupsQuerySet(
                client=obj.client,
                model=Group,
                endpoint=f"{obj.endpoint}/memberOf",
            )
            qs._user_id = obj.id  # type: ignore[attr-defined]
            return qs

        return property(fget=fget)

    def _iter_objects(self, data: dict[str, Any]) -> Iterator["Group"]:
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
