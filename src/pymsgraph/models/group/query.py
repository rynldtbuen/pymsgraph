from typing import TYPE_CHECKING, Any, cast

from pymsgraph import utils
from pymsgraph.models.query import QuerySet
from pymsgraph.utils import get_model_class

if TYPE_CHECKING:
    from pymsgraph.models.user import User
    from pymsgraph.models.directory_object import DirectoryObject


class UsersQuerySet(QuerySet["User"]):
    """
    Specialized queryset for user-only member projections.
    """

    def make_from_graph(self, data: dict[str, Any]) -> "User":
        """
        Materialize a `User` model from Graph payload.

        Args:
            data:
                Raw Graph object payload for a user.

        Returns:
            User:
                Hydrated user model bound to the current client.
        """
        model_class = cast(type["User"], get_model_class("User"))
        return model_class.from_graph(data, client=self._client, path=model_class.PATH)


class MembersQuerySet(QuerySet["DirectoryObject"]):
    """
    QuerySet for `/groups/{id}/members` directory objects.

    Supports heterogeneous member payloads (user/group/device/service principal,
    etc.) by resolving model type from `@odata.type`.
    """

    PATH = "/members"
    _ODATA_TYPE_MAP = {
        "#microsoft.graph.user": "User",
        "#microsoft.graph.group": "Group",
        "#microsoft.graph.device": "Device",
        "#microsoft.graph.servicePrincipal": "ServicePrincipal",
        "#microsoft.graph.orgContact": "OrganizationalContact",
        "#microsoft.graph.directoryObject": "DirectoryObject",
    }

    def _resolve_model_class(self, data: dict[str, Any]) -> type["DirectoryObject"]:
        """
        Resolve a concrete directory object model from `@odata.type`.
        """
        odata_type = (data.get("@odata.type") or "").lower()
        model_name = self._ODATA_TYPE_MAP.get(odata_type)
        if not model_name:
            return self._model_class
        try:
            return cast(type["DirectoryObject"], get_model_class(model_name))
        except Exception:
            return self._model_class

    def make_from_graph(self, data: dict[str, Any]) -> "DirectoryObject":
        """
        Materialize a typed directory object from Graph payload.

        Args:
            data:
                Raw Graph member payload, optionally including `@odata.type`.

        Returns:
            DirectoryObject:
                Hydrated model instance resolved from `@odata.type` when available.
        """
        model_class = self._resolve_model_class(data)
        return model_class.from_graph(data, client=self._client, path=model_class.PATH)

    @property
    def users(self) -> UsersQuerySet:
        """
        Return a user-only member queryset.

        This scopes members to `/members/microsoft.graph.user` and preserves
        compatible prefetched member cache data when available.

        Returns:
            UsersQuerySet:
                Queryset containing only user members.
        """
        cached_data = self._kwargs.get("cached_data")
        if cached_data:
            cached_data = [
                item
                for item in cached_data
                if (item.get("@odata.type") or "").lower() == "#microsoft.graph.user"
            ]

        return UsersQuerySet(
            self._client,
            path=f"{self.path}/microsoft.graph.user",
            model_class=cast(type["User"], get_model_class("User")),
            cached_data=cached_data,
        )

    async def add(self, *args: Any) -> None:
        """
        Add one or more directory objects to the group.

        Members are coerced from ids/models/querysets and submitted through
        Graph `$batch` in chunks of up to 20 `POST .../members/$ref` requests.

        Args:
            *args:
                Member identifiers or objects coercible to directory object ids.

        Returns:
            None

        Raises:
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.
            RuntimeError:
                If any batch item fails (`utils.raise_batch_errors`).
        """

        c = self._client
        objects = self._coerce_objects(args)

        for chunked_members in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for i, member in enumerate(chunked_members, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{self.path}/$ref",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "@odata.id": f"{c.base_url}/directoryObjects/{member.id}"
                        },
                    }
                )
            resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(resp, requests, action="add group members")

    async def remove(self, *args: Any) -> None:
        """
        Remove one or more members from the group.

        Members are coerced from ids/models/querysets and submitted through
        Graph `$batch` in chunks of up to 20 `DELETE .../members/{id}/$ref`
        requests.

        Args:
            *args:
                Member identifiers or objects coercible to directory object ids.

        Returns:
            None

        Raises:
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.
            RuntimeError:
                If any batch item fails (`utils.raise_batch_errors`).
        """

        c = self._client
        objects = self._coerce_objects(args)

        for chunked_members in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for i, member in enumerate(chunked_members, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "DELETE",
                        "url": f"{self.path}/{member.id}/$ref",
                    }
                )
            resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(resp, requests, action="remove group members")

    async def copy_to(self, *args: Any) -> None:
        """
        Copy all members in this queryset to one or more target groups.

        This first materializes current members, then issues batched
        `POST .../members/$ref` requests (20 per batch) for each target group.

        Args:
            *args:
                Target groups as ids/models/querysets coercible by `c.groups`.

        Returns:
            None

        Raises:
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.
            RuntimeError:
                If any batch item fails (`utils.raise_batch_errors`).
        """
        c = self._client
        groups = list(c.groups._coerce_objects(args))
        members = [m async for m in self]

        for group in groups:
            for chunked_members in utils.chunks(members, 20):
                requests: list[dict[str, Any]] = []
                for i, member in enumerate(chunked_members, start=1):
                    requests.append(
                        {
                            "id": str(i),
                            "method": "POST",
                            "url": f"{group.members.path}/$ref",
                            "headers": {"Content-Type": "application/json"},
                            "body": {
                                "@odata.id": f"{c.base_url}/directoryObjects/{member.id}"
                            },
                        }
                    )
                resp = await c.post("/$batch", body={"requests": requests})
                utils.raise_batch_errors(resp, requests, action="copy group members")
