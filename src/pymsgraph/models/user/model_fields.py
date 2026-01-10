from __future__ import annotations
from collections.abc import Iterable
from typing import TYPE_CHECKING, TypeAlias

from pymsgraph.models.fields import CharField, BooleanField, DateTimeField, Field
from pymsgraph.models.base import Model
from pymsgraph.models.query import QuerySet

if TYPE_CHECKING:
    from pymsgraph.models.group import Group


class PasswordProfile(Model):
    password = CharField()
    force_change_password_next_sign_in = BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = BooleanField(default=False)


class AssignedLicense(Model):
    endpoint = "/assignedLicense"

    sku_id = CharField()
    disabled_plans = Field()


class AssignedLicensesQuerySet(QuerySet[AssignedLicense]):
    model_class = AssignedLicense

    async def add(
        self, *args: str | AssignedLicense | QuerySet[AssignedLicense]
    ) -> None:
        """
        Add license/s to this user.
        """

        objects = self._coerce_objects(args, key="sku_id")
        if not objects:
            return

        response = await self._client.post(
            self._endpoint,
            body={
                "addLicenses": [
                    {"skuId": obj.id, "disabledPlans": []} for obj in objects
                ],
                "removeLicenses": [],
            },
        )

    # def remove(self, *args: assigned_license_arg_types) -> None:
    #     """
    #     Remove license/s from this user.
    #     """

    #     objects = list(utils.coerce_objects(*args, queryset=self))
    #     if not objects:
    #         return

    #     p = self._parent
    #     assert p is not None

    #     self._client.post(
    #         f"{p.endpoint}/assignLicense",
    #         json_body={
    #             "addLicenses": [],
    #             "removeLicenses": [obj.id for obj in objects],
    #         },
    #     )

    # @classmethod
    # def _compile_collection_lookup(cls, lookup: str, value: str) -> str:
    #     func = utils.compile_collection_lookup(
    #         field_name="assigned_licenses", element_field=True, var="u"
    #     )
    #     return func(lookup, value)


class AssignedPlans(Model):
    read_only = True

    assigned_date_time = DateTimeField()
    capability_status = CharField()
    service = CharField()
    service_plan_id = CharField()


class AssignedPlansQuerySet(QuerySet[AssignedPlans]):
    model_class = AssignedPlans


class EmployeeOrgData(Model):
    cost_center = CharField()
    division = CharField()


class MemberOfQuerySet(QuerySet["Group"]):
    endpoint = "/memberOf"
