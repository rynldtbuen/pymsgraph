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

        objects: list[AssignedLicense] = []
        requested: dict[str, int] = {}
        get_subscribed_sku_cache: Callable[[str], "SubscribedSku | None"] = (
            await self._client.subscribed_skus._get_subscribed_skus_cache()
        )
        for obj in self._coerce_objects(args, key="sku_id"):
            if obj.sku_id is None:
                continue
            subscribed_sku = get_subscribed_sku_cache(obj.sku_id)
            if subscribed_sku is None:
                raise ValueError(f"Unknown sku_id: {obj.sku_id}")

            requested[obj.sku_id] = requested.get(obj.sku_id, 0) + 1
            if requested[obj.sku_id] > subscribed_sku.available_units:
                name = subscribed_sku.product_name
                label = f"{obj.sku_id} ({name})" if name else obj.sku_id
                raise ValueError(f"No available units for sku_id: {label}")
            objects.append(obj)
        if not objects:
            return

        kwargs = {
            "path": self.path,
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

    # def filter(self, **kwargs: Any) -> UserQuerySet:
    #     exprs = self._parent._params.setdefault("$filter", [])
    #     for key, value in kwargs.items():
    #         if "__" in key:
    #             field, lookup = key.split("__", 1)
    #         else:
    #             field, lookup = key, "exact"

    #         if field == "isnull":
    #             if not isinstance(value, bool):
    #                 raise ValueError(f"Value is not an instance of bool, {value!r}")
    #             expr = (
    #                 "assignedLicenses/$count eq 0"
    #                 if value
    #                 else "assignedLicenses/$count ne 0"
    #             )
    #             if expr not in exprs:
    #                 exprs.append(expr)
    #             continue

    #         if field != "sku_id":
    #             raise ValueError(f"Unsupported field for assignedLicenses: {field!r}")

    #         try:
    #             func = PY_TO_ODATA_QUERY[lookup]
    #         except KeyError:
    #             raise ValueError(f"Unsupported lookup: {lookup!r}") from None

    #         clause = func("u/skuId", value)
    #         expr = f"assignedLicenses/any(u:{clause})"
    #         if expr not in exprs:
    #             exprs.append(expr)
    #     return self._parent

    async def add(self, *args: "str | AssignedLicense", force=False) -> None:
        """
        Add license(s) to all users in this queryset.

        Usage:
            client.users.filter(...).assigned_licenses.add("sku1", AssignLicense(sku_id="sku2"))
        """

        c = self._parent._client
        objects = list(
            AssignedLicensesQuerySet(self._parent._client)._coerce_objects(
                args, key="sku_id"
            )
        )
        if not objects:
            return

        async for chunked_users in utils.achunks(self._parent.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for i, u in enumerate(chunked_users, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{u.path}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "addLicenses": [
                                {"skuId": obj.id, "disabledPlans": []}
                                for obj in objects
                            ],
                            "removeLicenses": [],
                        },
                    }
                )

            batch_resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="add user queryset licenses")

    async def remove(
        self, *args: str | AssignedLicense, force=False, all=False
    ) -> None:
        """
        Remove license(s) from all users in this queryset.

        Usage:
            client.users.filter(...).assigned_licenses.remove("sku1", AssignLicense(sku_id="sku2"))
        """

        c = self._parent._client
        objects = list(
            AssignedLicensesQuerySet(self._parent._client)._coerce_objects(
                args, key="sku_id"
            )
        )
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
                            "removeLicenses": [obj.id for obj in objects],
                        },
                    }
                )

            batch_resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="remove user queryset licenses")


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
