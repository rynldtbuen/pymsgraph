from typing import ClassVar
from pymsgraph.fields import CharField, IntegerField, ObjectField
from pymsgraph.models.base import Model
from pymsgraph.query import Capabilities, QuerySet


class LicenseUnitsDetail(Model):
    """
    Graph licenseUnitsDetail resource type

    https://learn.microsoft.com/en-us/graph/api/resources/licenseunitsdetail?view=graph-rest-1.0
    """

    is_read_only = True

    enabled = IntegerField()
    locked_out = IntegerField()
    suspended = IntegerField()
    warning = IntegerField()

    @classmethod
    def as_descriptor(cls):
        return ObjectField(cls)

    def __repr__(self):
        return f"<LicenseUnitsDetail: enabled={self.enabled}, locked_out={self.locked_out}, suspended={self.suspended}, warning={self.warning}>"


class ServicePlanInfo(Model):
    """
    Graph servicePlanInfo resource type

    https://learn.microsoft.com/en-us/graph/api/resources/serviceplaninfo?view=graph-rest-1.0
    """

    is_read_only = True

    applies_to = CharField(read_only=True)
    provisioning_status = CharField(read_only=True)
    id = CharField(read_only=True, graph_name="servicePlanId")
    name = CharField(read_only=True, graph_name="servicePlanName")

    @classmethod
    def as_descriptor(cls):
        return ObjectField(cls, many=True)

    def __repr__(self):
        return f"<ServicePlanInfo: {self.name}>"


class SubscribedSku(Model):
    """
    Graph subscribedSku resource type

    https://learn.microsoft.com/en-us/graph/api/subscribedsku-list?view=graph-rest-1.0&tabs=http
    """

    is_read_only = True

    sku_id = CharField()  # skuId
    sku_part_number = CharField()  # skuPartNumber
    capability_status = CharField()  # capabilityStatus
    consumed_units = IntegerField()  # consumedUnits (int)
    applies_to = CharField()  # appliesTo (often "User")
    prepaid_units = LicenseUnitsDetail.as_descriptor()
    service_plans = ServicePlanInfo.as_descriptor()

    endpoint = "/subscribedSkus"

    def __repr__(self):
        return f"<SubscribedSku: {self.sku_id}>"


class SubscribedSkuQuerySet(QuerySet[SubscribedSku]):
    model_class = SubscribedSku
    capabilities = Capabilities.read_only()
