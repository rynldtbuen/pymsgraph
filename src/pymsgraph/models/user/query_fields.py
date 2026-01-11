from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pymsgraph import utils
from pymsgraph.models.directory_object import DirectoryObject
from pymsgraph.models.fields import QuerySetField
from pymsgraph.models.query import QuerySet
from pymsgraph.utils import get_model_class

from .model_fields import AssignedLicense, AssignedPlans

if TYPE_CHECKING:
    from pymsgraph.models.directory_object import DirectoryObject

    from pymsgraph.models.user import User
    from pymsgraph.models.group import Group


class AssignedLicensesQuerySet(QuerySet[AssignedLicense]):
    model_class = AssignedLicense

    async def add(
        self,
        *args: str | AssignedLicense | QuerySet[AssignedLicense],
        as_batch: bool = False,
    ) -> dict[str, Any] | None:
        """
        Add license/s to this user.
        """

        objects = self._coerce_objects(args, key="sku_id")
        if not objects:
            return

        kwargs = {
            "path": self._endpoint,
            "body": {
                "addLicenses": [
                    {"skuId": obj.sku_id, "disabledPlans": []} for obj in objects
                ],
                "removeLicenses": [],
            },
        }

        if as_batch:
            return kwargs

        await self._client.post(**kwargs)

    async def remove(
        self,
        *args: str | AssignedLicense | QuerySet[AssignedLicense],
        as_batch: bool = False,
    ) -> dict[str, Any] | None:
        """
        Remove license/s from this user.
        """

        objects = self._coerce_objects(args, key="sku_id")
        if not objects:
            return

        kwargs = {
            "path": self._endpoint,
            "body": {
                "addLicenses": [],
                "removeLicenses": [obj.sku_id for obj in objects],
            },
        }

        if as_batch:
            return kwargs

        await self._client.post(**kwargs)


class AssignedPlansQuerySet(QuerySet[AssignedPlans]):
    model_class = AssignedPlans


class GroupsQuerySet(QuerySet["Group"]):

    async def add(self, *args: "str | Group  | QuerySet[Group]") -> None:
        """
        Add group/s to this user.
        """
        c = self._client
        groups = c.groups._coerce_objects(args)
        obj: "User" = self._kwargs["obj"]

        for chunk_groups in utils.chunks(groups, 20):
            requests: list[dict[str, Any]] = []
            for i, g in enumerate(chunk_groups, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{g.members._endpoint}/$ref",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "@odata.id": f"{c.base_url}/directoryObjects/{obj.directory_object_id}"
                        },
                    }
                )

            resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(resp, action="add user to groups")

    async def remove(self, *args: "str | Group  | QuerySet[Group]") -> None:
        """
        Remove group/s from this user.
        """

        c = self._client
        groups = c.groups._coerce_objects(args)
        obj: "User" = self._kwargs["obj"]

        for chunk_groups in utils.chunks(groups, 20):
            requests: list[dict[str, Any]] = []
            for i, g in enumerate(chunk_groups, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "DELETE",
                        "url": f"{g.members._endpoint}/{obj.directory_object_id}/$ref",
                    }
                )
            resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(resp, action="remove user from groups")

    # def _iter_objects(self, data: dict[str, Any]) -> Iterator["Group"]:
    #     for item in data.get("value", []):
    #         otype = item.get("@odata.type")
    #         if otype and otype.lower() != "#microsoft.graph.group":
    #             continue
    #         yield self.model_class(graph_data=item, qs=self)


class MemberOfQuerySet(QuerySet["DirectoryObject"]):
    endpoint = "/memberOf"
    _ODATA_TYPE_MAP = {
        "#microsoft.graph.group": "Group",
        "#microsoft.graph.directoryrole": "DirectoryRole",
        "#microsoft.graph.administrativeunit": "AdministrativeUnit",
    }

    def _resolve_model_class(self, data: dict[str, Any]) -> type[DirectoryObject]:
        odata_type = (data.get("@odata.type") or "").lower()
        model_name = self._ODATA_TYPE_MAP.get(odata_type)
        if not model_name:
            raise RuntimeError(f"Unsupported member of model class, '{odata_type}'")
        try:
            model_class = cast(type[DirectoryObject], get_model_class(model_name))
            return model_class
        except Exception:
            return self._model_class

    def make_from_graph(self, data: dict[str, Any]) -> DirectoryObject:
        model_class = self._resolve_model_class(data)
        return model_class.from_graph(
            data, client=self._client, endpoint=self._endpoint
        )

    @property
    def groups(self) -> "GroupsQuerySet":
        parent_user = self._kwargs.get("obj")
        if parent_user is None:
            raise ValueError("MemberOfQuerySet has no parent user bound.")

        cached = self._kwargs.get("cached_data")
        if cached:
            cached = [
                item
                for item in cached
                if (item.get("@odata.type") or "").lower() == "#microsoft.graph.group"
            ]

        return GroupsQuerySet(
            self._client,
            endpoint=f"{self._endpoint}/microsoft.graph.group",
            model_class=cast(type["Group"], get_model_class("Group")),
            obj=parent_user,
            cached_data=cached,
        )
