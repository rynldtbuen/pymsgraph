from __future__ import annotations

from pymsgraph.models.base import Model
from pymsgraph.models.fields import BooleanField, CharField, DateTimeField, Field
from pymsgraph.models.subscribed_sku import SubscribedSku


class PasswordProfile(Model):
    password = CharField()
    force_change_password_next_sign_in = BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = BooleanField(default=False)


class AssignedLicense(Model):
    endpoint = "/assignLicense"

    sku_id = CharField()
    disabled_plans = Field()

    @property
    def product_name(self):
        return SubscribedSku.get_product_name(sku_id=self.sku_id)


class AssignedPlans(Model):
    read_only = True

    assigned_date_time = DateTimeField()
    capability_status = CharField()
    service = CharField()
    service_plan_id = CharField()


class EmployeeOrgData(Model):
    cost_center = CharField()
    division = CharField()
