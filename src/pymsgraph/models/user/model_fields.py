from typing import Any

from pymsgraph.models.fields import CharField, BooleanField, Field
from pymsgraph.models.base import Model
from pymsgraph.models.query import QuerySet


class PasswordProfile(Model):
    password = CharField()
    force_change_password_next_sign_in = BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = BooleanField(default=False)


class AssignedLicense(Model):
    disabled_plans = Field()
    sku_id = CharField()


class AssignedLicensesQuerySet(QuerySet[AssignedLicense]):
    pass
