from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from pymsgraph import utils
from pymsgraph.models.directory_object import DirectoryObject
from pymsgraph.models.query import QuerySet
from pymsgraph.models.subscribed_sku import SubscribedSku
from pymsgraph.utils import get_model_class

from .common import AssignedLicense, AssignedPlans

if TYPE_CHECKING:
    from pymsgraph.models.group import Group
    from pymsgraph.models.user import User, UserQuerySet
    from pymsgraph.models.subscribed_sku import SubscribedSku


class AssignedLicensesQuerySet(QuerySet[AssignedLicense]):
    model_class = AssignedLicense

    async def add(
        self,
        *args: "str | AssignedLicense",
        as_batch: bool = False,
    ) -> dict[str, Any] | None:
        """
        Add license/s to this user.
        """

        available: dict[str, "SubscribedSku"] = {}
        subscribed_sku_cache = self._client.subscribed_skus._cache
        for obj in self._coerce_objects(args, key="sku_id"):
            if obj.sku_id is None:
                continue
            subscribed_sku = await subscribed_sku_cache.get(obj.sku_id)
            if subscribed_sku is None:
                raise ValueError(f"Unknown sku_id: {obj.sku_id}")

            if not subscribed_sku.has_available_units():
                name = subscribed_sku.product_name
                label = f"{obj.sku_id} ({name})" if name else obj.sku_id
                raise ValueError(f"No available units for sku_id: {label}")
            available[obj.sku_id] = subscribed_sku

        if not available:
            return

        kwargs = {
            "path": self.path,
            "body": {
                "addLicenses": [
                    {"skuId": sku_id, "disabledPlans": []}
                    for sku_id in available.keys()
                ],
                "removeLicenses": [],
            },
        }

        if as_batch:
            return kwargs

        await self._client.post(**kwargs)
        for subscribed_sku in available.values():
            current = subscribed_sku._data.get(
                "consumed_units", subscribed_sku.consumed_units or 0
            )
            subscribed_sku._data["consumed_units"] = int(current) + 1

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
            "path": self.path,
            "body": {
                "addLicenses": [],
                "removeLicenses": [obj.sku_id for obj in objects],
            },
        }

        if as_batch:
            return kwargs

        await self._client.post(**kwargs)


class AssignedLicensesQuerySetProxy:
    def __init__(self, parent: "UserQuerySet"):
        self._parent = parent

    async def add(
        self, *args: "str | AssignedLicense", force=False
    ) -> dict[str, dict[str, int]]:
        """
        Add license(s) to all users in this queryset.

        Usage:
            client.users.filter(...).assigned_licenses.add("sku1", AssignLicense(sku_id="sku2"))
        """

        c = self._parent._client
        available: dict[str, "SubscribedSku"] = {}
        subscribed_sku_cache = c.subscribed_skus._cache
        for obj in AssignedLicensesQuerySet(c)._coerce_objects(args, key="sku_id"):
            if obj.sku_id is None:
                continue
            subscribed_sku = await subscribed_sku_cache.get(obj.sku_id)
            if subscribed_sku is None:
                raise ValueError(f"Unknown sku_id: {obj.sku_id}")
            if not subscribed_sku.has_available_units():
                name = subscribed_sku.product_name
                label = f"{obj.sku_id} ({name})" if name else obj.sku_id
                raise ValueError(f"No available units for sku_id: {label}")
            available[obj.sku_id] = subscribed_sku

        if not available:
            return {}

        remaining = {k: v.available_units for k, v in available.items()}
        assigned_counts = {k: 0 for k in available}
        total_users = 0
        async for chunked_users in utils.achunks(self._parent.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for i, u in enumerate(chunked_users, start=1):
                total_users += 1
                add: list[dict[str, Any]] = []
                for sku_id in available.keys():
                    if remaining[sku_id] > 0:
                        add.append({"skuId": sku_id, "disabledPlans": []})
                        remaining[sku_id] -= 1
                        assigned_counts[sku_id] += 1
                if not add:
                    continue
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{u.path}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "addLicenses": add,
                            "removeLicenses": [],
                        },
                    }
                )

            batch_resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="add user queryset licenses")
            for sku_id, subscribed_sku in available.items():
                current = subscribed_sku._data.get(
                    "consumed_units", subscribed_sku.consumed_units or 0
                )
                used = assigned_counts.get(sku_id, 0)
                subscribed_sku._data["consumed_units"] = int(current) + used

        return {
            sku_id: {"assigned": assigned, "skipped": total_users - assigned}
            for sku_id, assigned in assigned_counts.items()
        }

    async def remove(
        self, *args: str | AssignedLicense, force=False, all=False
    ) -> None:
        """
        Remove license(s) from all users in this queryset.

        Usage:
            client.users.filter(...).assigned_licenses.remove("sku1", AssignLicense(sku_id="sku2"))
        """

        c = self._parent._client
        objects = list(AssignedLicensesQuerySet(c)._coerce_objects(args, key="sku_id"))

        subscribed_sku_cache = c.subscribed_skus._cache
        subscribed_skus: dict[str, SubscribedSku] = {}
        for obj in objects:
            sku_id = obj.sku_id
            subscribed_sku = await subscribed_sku_cache.get(sku_id)
            if subscribed_sku is None:
                raise ValueError(f"Unknown sku_id: {obj.sku_id}")
            subscribed_skus[sku_id] = subscribed_sku

        if not objects:
            return

        async for chunked_users in utils.achunks(self._parent.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for i, u in enumerate(chunked_users, start=1):
                u = cast("User", u)
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{u.path}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "addLicenses": [],
                            "removeLicenses": [
                                sku_id for sku_id in subscribed_skus.keys()
                            ],
                        },
                    }
                )

            batch_resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="remove user queryset licenses")
            user_count = len(requests)
            for sku_id, subscribed_sku in subscribed_skus.items():
                current = subscribed_sku._data.get(
                    "consumed_units", subscribed_sku.consumed_units or 0
                )
                subscribed_sku._data["consumed_units"] = max(
                    0, int(current) - user_count
                )


class AssignedPlansQuerySet(QuerySet[AssignedPlans]):
    model_class = AssignedPlans


class GroupsQuerySet(QuerySet["Group"]):
    def make_from_graph(self, data: dict[str, Any]) -> "Group":
        model_class = cast(type["Group"], get_model_class("Group"))
        return model_class.from_graph(data, client=self._client, path=model_class.PATH)

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
                        "url": f"{g.members.path}/$ref",
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
                        "url": f"{g.members.path}/{obj.directory_object_id}/$ref",
                    }
                )
            resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(resp, action="remove user from groups")

    async def copy_to(self, *args: "str | User | QuerySet[User]") -> None:
        """
        Copy groups in this queryset to other user(s).
        """
        c = self._client
        users = list(c.users._coerce_objects(args))
        if not users:
            return

        groups = [g async for g in self if g.group_type != g.DISTRIBUTION]
        if not groups:
            return

        for user in users:
            if not getattr(user, "id", None):
                raise ValueError("User id is required for copy_to")
            for chunk_groups in utils.chunks(groups, 20):
                requests: list[dict[str, Any]] = []
                for i, g in enumerate(chunk_groups, start=1):
                    requests.append(
                        {
                            "id": str(i),
                            "method": "POST",
                            "url": f"{g.members.path}/$ref",
                            "headers": {"Content-Type": "application/json"},
                            "body": {
                                "@odata.id": f"{c.base_url}/directoryObjects/{user.id}"
                            },
                        }
                    )
                resp = await c.post("/$batch", body={"requests": requests})
                utils.raise_batch_errors(resp, action="copy user groups")


class MemberOfQuerySet(QuerySet["DirectoryObject"]):
    PATH = "/memberOf"
    _ODATA_TYPE_MAP = {
        "#microsoft.graph.group": "Group",
        "#microsoft.graph.directoryRole": "DirectoryRole",
        "#microsoft.graph.administrativeUnit": "AdministrativeUnit",
    }

    model_class = DirectoryObject

    def _resolve_model_class(self, data: dict[str, Any]) -> type[DirectoryObject]:
        if (odata_type := data.get("@odata.type")) is None:
            raise RuntimeError("@odata_type is required from graph data.")
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
        return model_class.from_graph(data, client=self._client, path=model_class.PATH)

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
            path=f"{self.path}/microsoft.graph.group",
            model_class=cast(type["Group"], get_model_class("Group")),
            obj=parent_user,
            cached_data=cached,
        )
