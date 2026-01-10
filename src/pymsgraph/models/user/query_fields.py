from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pymsgraph.models.query import QuerySet

from .model_fields import AssignedLicense, AssignedPlans

if TYPE_CHECKING:
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


class MemberOfQuerySet(QuerySet["Group"]):
    endpoint = "/memberOf"
