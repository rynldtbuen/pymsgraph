from __future__ import annotations

from pymsgraph.models.fields import CharField, BooleanField, Field
from pymsgraph.models.base import Model
from pymsgraph.models.query import QuerySet


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


# class MemberOfQuerySet(QuerySet[AssignedLicense]):
#     endpoint = "/assignedLicense"
#     model_class = "AssignedLicense"
