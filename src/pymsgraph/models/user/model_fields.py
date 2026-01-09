from __future__ import annotations
from typing import TYPE_CHECKING

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

    def add(self, *args): ...
    def remove(self, *args): ...


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
