from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, TypeAlias

from pymsgraph import utils
from pymsgraph.manager import TModel
from pymsgraph.query import Capabilities, QuerySet

if TYPE_CHECKING:
    from ..user import User

arg_types: TypeAlias = "str | User | Iterable[str] | Iterable[User] | QuerySet[User]"


class OwnersQuerySet(QuerySet["User"]):
    model_class = "User"  # pyright: ignore[reportAssignmentType]
    capabilities = Capabilities.read_only()

    def add(self, *args: arg_types) -> None:
        """
        Add one or more owners to this group.
        """
        group = self._get_object()
        objects = utils.coerce_objects(*args, model_class=self.model_class)

        client = self._client
        for users in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for idx, user in enumerate(users, start=1):
                requests.append(
                    {
                        "id": str(idx),
                        "method": "POST",
                        "url": f"{group.endpoint}/owners/$ref",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "@odata.id": f"{client.base_url}/directoryObjects/{user.id}"
                        },
                    }
                )
            resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="add owners")

    def remove(self, *args: arg_types) -> None:
        """
        Remove one or more owners from this group.
        """
        group = self._get_object()
        objects = utils.coerce_objects(*args, model_class=self.model_class)

        client = self._client
        for users in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for index, user in enumerate(users, start=1):
                requests.append(
                    {
                        "id": str(index),
                        "method": "DELETE",
                        "url": f"{group.endpoint}/owners/{user.id}/$ref",
                    }
                )
            resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="remove owners")
