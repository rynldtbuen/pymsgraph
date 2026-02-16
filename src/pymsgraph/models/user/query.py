from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from pymsgraph import utils
from pymsgraph.models.directory_object import DirectoryObject
from pymsgraph.models.query import QuerySet
from pymsgraph.models.service_principal.query import (
    AppRoleAssignmentQuerySet as _AppRoleAssignmentQuerySet,
)
from pymsgraph.models.service_principal import ServicePrincipal
from pymsgraph.models.service_principal.common import AppRoleAssignment
from pymsgraph.models.subscribed_sku import SubscribedSku
from pymsgraph.utils import get_model_class

from .common import AssignedLicense, AssignedPlans

if TYPE_CHECKING:
    from pymsgraph.models.group import Group
    from pymsgraph.models.service_principal.common import AppRoleAssignment
    from pymsgraph.models.subscribed_sku import SubscribedSku
    from pymsgraph.models.user import User, UserQuerySet


class AssignedLicensesQuerySet(QuerySet[AssignedLicense]):
    model_class = AssignedLicense

    async def add(
        self,
        *args: "str | AssignedLicense",
        as_batch_request: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Add one or more licenses to a single user.

        This method targets the user bound to this queryset path (for example
        `/users/{id}/assignLicense`). Inputs may be SKU ids, product names, or
        `AssignedLicense` objects. Product names are resolved to SKU ids when
        possible through `SubscribedSku.get_sku_id(...)`.

        Args:
                *args:
                        Licenses to add. Supported values:
                        - SKU id string
                        - Product name string (resolvable to SKU id)
                        - `AssignedLicense` object
                as_batch_request:
                        When `True`, do not call Graph. Return a batch request
                        item payload instead.
                request_id:
                        Optional request id included when `as_batch_request=True`.

        Returns:
                dict[str, Any] | None:
                        - Batch mode: request payload dict.
                        - Non-batch mode: `None`.
                        - `None` if no valid licenses are provided.

        Raises:
                ValueError:
                        If any SKU id is unknown or has no available units.
                httpx.HTTPStatusError:
                        If Microsoft Graph returns an HTTP error.

        Notes:
                - Uses `POST {path}` with `addLicenses` payload.
                - On successful non-batch calls, local `SubscribedSku.consumed_units`
                  cache is incremented by 1 for each added SKU.
        """

        _args: list[str | AssignedLicense] = []
        for arg in args:
            if isinstance(arg, str) and not utils.is_guid(arg):
                sku_id = SubscribedSku.get_sku_id(product_name=arg)
                if sku_id is not None:
                    _args.append(sku_id)
                else:
                    _args.append(arg)
            else:
                _args.append(arg)

        available: dict[str, "SubscribedSku"] = {}
        subscribed_sku_cache = self._client.subscribed_skus._cache
        for obj in self._coerce_objects(args=tuple(_args), key="sku_id"):
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

        if as_batch_request:
            return {"id": request_id, **kwargs}

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
        Remove one or more licenses from a single user.

        This method targets the user bound to this queryset path and sends
        `removeLicenses` via Graph `assignLicense` API.

        Args:
                *args:
                        Licenses to remove. Supported values:
                        - SKU id string
                        - `AssignedLicense` object
                        - `QuerySet[AssignedLicense]`
                as_batch:
                        When `True`, do not call Graph. Return request kwargs
                        payload for inclusion in a `$batch` request.

        Returns:
                dict[str, Any] | None:
                        - Batch mode: request kwargs dict.
                        - Non-batch mode: `None`.
                        - `None` if no licenses are provided after coercion.

        Raises:
                httpx.HTTPStatusError:
                        If Microsoft Graph returns an HTTP error.
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
    """
    Proxy facade for bulk assigned-license operations on a `UserQuerySet`.

    Exposes convenience methods that operate over all users matched by the
    parent queryset, using Graph `$batch` requests under the hood.
    """

    def __init__(self, parent: "QuerySet[User]"):
        self._parent = parent

    async def add(
        self, *args: "str | AssignedLicense", force=False
    ) -> dict[str, dict[str, int]]:
        """
        Add one or more licenses to all users in the parent queryset.

        Each input item is normalized to an `AssignedLicense` and validated
        against `client.subscribed_skus` cache. The operation is executed with
        Graph `$batch` requests (up to 20 users per batch). License assignment
        respects available units per SKU and skips users once capacity is
        exhausted.

        Args:
                *args:
                        License identifiers to add. Each item can be:
                        - SKU id string
                        - `AssignedLicense` instance

        Returns:
                dict[str, dict[str, int]]:
                        Per-SKU summary with:
                        - `assigned`: number of users assigned the SKU
                        - `skipped`: number of users not assigned due to capacity

        Raises:
                ValueError:
                        If a SKU id is unknown or has no available units.
                httpx.HTTPStatusError:
                        If Microsoft Graph returns an error for any batch request.

        Notes:
                - Batch requests call `POST /users/{id}/assignLicense`.
                - `SubscribedSku.consumed_units` cache is updated after success.

        Quick usage:
                ```python
                summary = await client.users.filter(account_enabled=True).assigned_licenses.add(
                        "6fd2c87f-b296-42f0-b197-1e91e994b900"
                )
                print(summary)
                ```
        """

        # TODO: allow passing the product name and resolve it via SubscribedSku.get_sku_id

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
            utils.raise_batch_errors(
                batch_resp, requests, action="add user queryset licenses"
            )
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
        self, *args: str | AssignedLicense, force: bool = False, all: bool = False
    ) -> None:
        """sss
        Remove one or more licenses from all users in the parent queryset.

        Input items are normalized to `AssignedLicense` objects, then each user
        is processed via Graph `$batch` requests (up to 20 users per batch).
        For each user, all requested SKU ids are sent in a single
        `assignLicense` request with `addLicenses=[]`.

        Args:
                *args:
                        License identifiers to remove. Each item can be:
                        - SKU id string
                        - `AssignedLicense` instance
                force:
                        Reserved for compatibility. Currently has no effect.
                all:
                        Reserved for compatibility. Currently has no effect.

        Returns:
                None

        Raises:
                ValueError:
                        If a SKU id is unknown.
                httpx.HTTPStatusError:
                        If Microsoft Graph returns an error for any batch request.

        Notes:
                - Batch requests call `POST /users/{id}/assignLicense`.
                - `SubscribedSku.consumed_units` cache is decreased after success.

        Quick usage:
                ```python
                await client.users.filter(department="IT").assigned_licenses.remove(
                        "6fd2c87f-b296-42f0-b197-1e91e994b900"
                )
                ```
        """

        # TODO: allow passing the product name and resolve it via SubscribedSku.get_sku_id

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
            utils.raise_batch_errors(
                batch_resp, requests, action="remove user queryset licenses"
            )
            user_count = len(requests)
            for sku_id, subscribed_sku in subscribed_skus.items():
                current = subscribed_sku._data.get(
                    "consumed_units", subscribed_sku.consumed_units or 0
                )
                subscribed_sku._data["consumed_units"] = max(
                    0, int(current) - user_count
                )


class AppRoleAssignmentsQuerySetProxy:
    def __init__(self, parent: "QuerySet[User]"):
        self._parent = parent

    async def add(self, *args: "AppRoleAssignment | dict[str, str]") -> None:
        """
        Assign app roles to all users in this queryset.
        """

        c = self._parent._client
        assignments = list(AppRoleAssignmentQuerySet(c)._coerce_objects(args))
        if not assignments:
            return
        for obj in assignments:
            if not obj.resource_id or not obj.app_role_id:
                raise ValueError("resource_id and app_role_id are required.")

        async for chunked_users in utils.achunks(self._parent.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for u in chunked_users:
                for obj in assignments:
                    requests.append(
                        {
                            "id": str(len(requests) + 1),
                            "method": "POST",
                            "url": f"/servicePrincipals/{obj.resource_id}/appRoleAssignedTo",
                            "headers": {"Content-Type": "application/json"},
                            "body": {
                                "principalId": u.id,
                                "resourceId": obj.resource_id,
                                "appRoleId": obj.app_role_id,
                            },
                        }
                    )
            for chunked_requests in utils.chunks(requests, 20):
                batch_resp = await c.post(
                    "/$batch", body={"requests": chunked_requests}
                )
                utils.raise_batch_errors(
                    batch_resp,
                    chunked_requests,
                    action="add user app role assignments",
                )

    async def remove(self, *args: "AppRoleAssignment | dict[str, str]") -> None:
        """
        Remove app roles from all users in this queryset.
        """

        c = self._parent._client
        assignments = list(AppRoleAssignmentQuerySet(c)._coerce_objects(args))
        if not assignments:
            return
        criteria = set()
        for obj in assignments:
            if not obj.resource_id or not obj.app_role_id:
                raise ValueError("resource_id and app_role_id are required.")
            criteria.add((obj.resource_id, obj.app_role_id))

        async for chunked_users in utils.achunks(self._parent.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for u in chunked_users:
                requests.append(
                    {
                        "id": str(len(requests) + 1),
                        "method": "GET",
                        "url": f"{u.path}/appRoleAssignments",
                    }
                )
            batch_resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(
                batch_resp, requests, action="list user app role assignments"
            )

            delete_requests: list[dict[str, Any]] = []
            for resp in batch_resp.get("responses", []) or []:
                body = resp.get("body") or {}
                for item in body.get("value", []) or []:
                    resource_id = item.get("resourceId")
                    app_role_id = item.get("appRoleId")
                    if (resource_id, app_role_id) not in criteria:
                        continue
                    assignment_id = item.get("id")
                    if not assignment_id or not resource_id:
                        continue
                    delete_requests.append(
                        {
                            "id": str(len(delete_requests) + 1),
                            "method": "DELETE",
                            "url": f"/servicePrincipals/{resource_id}/appRoleAssignedTo/{assignment_id}",
                        }
                    )

            for chunked_requests in utils.chunks(delete_requests, 20):
                batch_delete = await c.post(
                    "/$batch", body={"requests": chunked_requests}
                )
                utils.raise_batch_errors(
                    batch_delete,
                    chunked_requests,
                    action="remove user app role assignments",
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
            utils.raise_batch_errors(resp, requests, action="add user to groups")

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
            utils.raise_batch_errors(resp, requests, action="remove user from groups")

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
                utils.raise_batch_errors(resp, requests, action="copy user groups")


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


class AppRoleAssignmentQuerySet(_AppRoleAssignmentQuerySet):
    async def add(
        self, *args: "AppRoleAssignment | dict[str, str]"
    ) -> "AppRoleAssignment | list[AppRoleAssignment] | None":
        """
        Assign app roles to this user using /servicePrincipals/{id}/appRoleAssignedTo.
        """

        parent_user = self._kwargs.get("obj")
        if parent_user is None or parent_user.id is None:
            raise ValueError("AppRoleAssignmentQuerySet has no parent user bound.")

        c = self._client
        objects = self._coerce_objects(args)

        for chunked_objects in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for i, obj in enumerate(chunked_objects, start=1):
                if not obj.resource_id or not obj.app_role_id:
                    raise ValueError("resource_id and app_role_id are required.")
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"/servicePrincipals/{obj.resource_id}/appRoleAssignedTo",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "principalId": parent_user.id,
                            "resourceId": obj.resource_id,
                            "appRoleId": obj.app_role_id,
                        },
                    }
                )
            batch_resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(
                batch_resp, requests, action="add user app role assignments"
            )

    async def remove(self, *args: "AppRoleAssignment | dict[str, str]") -> None:
        """
        Remove app role assignments from this user using
        /servicePrincipals/{id}/appRoleAssignedTo/{assignmentId}.
        """

        parent_user = self._kwargs.get("obj")
        if parent_user is None or parent_user.id is None:
            raise ValueError("AppRoleAssignmentQuerySet has no parent user bound.")

        c = self._client
        objects = self._coerce_objects(args)

        for chunked_objects in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for i, obj in enumerate(chunked_objects, start=1):
                if not obj.id or not obj.resource_id:
                    raise ValueError("id and resource_id are required to remove.")
                requests.append(
                    {
                        "id": str(i),
                        "method": "DELETE",
                        "url": f"/servicePrincipals/{obj.resource_id}/appRoleAssignedTo/{obj.id}",
                    }
                )
            batch_resp = await c.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(
                batch_resp, requests, action="remove user app role assignments"
            )
