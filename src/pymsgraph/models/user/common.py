from __future__ import annotations

from pymsgraph.models.base import PropertyModel, ReadOnlyModel
from pymsgraph.models.fields import BooleanField, CharField, DateTimeField, Field
from pymsgraph.models.subscribed_sku import SubscribedSku


class PasswordProfile(PropertyModel):
    password = CharField()
    force_change_password_next_sign_in = BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = BooleanField(default=False)


class AssignedLicense(PropertyModel, ReadOnlyModel):
    PATH = "/assignLicense"

    sku_id = CharField()
    disabled_plans = Field()

    @property
    def id(self):
        return self.sku_id

    @property
    def product_name(self):
        return SubscribedSku.get_product_name(sku_id=self.sku_id)


class AssignedPlans(PropertyModel, ReadOnlyModel):
    assigned_date_time = DateTimeField()
    capability_status = CharField()
    service = CharField()
    service_plan_id = CharField()


class EmployeeOrgData(PropertyModel):
    cost_center = CharField()
    division = CharField()
