from typing import TYPE_CHECKING, Any
from pymsgraph.models.query import QuerySet

if TYPE_CHECKING:
    from pymsgraph.models.user import User


class MembersQuerySet(QuerySet["User"]):
    endpoint = "/members"

    async def add(self, *directory_object_ids: str, as_batch: bool = False) -> None:
        c = self._client
        batch_requests: list[dict[str, Any]] = []
        for dir_obj_id in directory_object_ids:
            body = {
                "method": "POST",
                "url": f"{self._endpoint}/$ref",
                "headers": {"Content-Type": "application/json"},
                "body": {"@odata.id": f"{c.base_url}/directoryObjects/{dir_obj_id}"},
            }
            batch_requests.append(body)
