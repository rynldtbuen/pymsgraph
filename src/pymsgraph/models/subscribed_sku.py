from dataclasses import dataclass
from typing import Any
from pymsgraph.fields import CharField, IntegerField, ObjectField
from pymsgraph.models.base import GraphModel


@dataclass(frozen=True, slots=True)
class LicenseUnitsDetail:
    enabled: int
    locked_out: int
    suspended: int
    warning: int

    @classmethod
    def from_graph(cls, payload: dict[str, Any]) -> "LicenseUnitsDetail":
        return cls(
            enabled=int(payload.get("enabled", 0) or 0),
            locked_out=int(payload.get("lockedOut", 0) or 0),
            suspended=int(payload.get("suspended", 0) or 0),
            warning=int(payload.get("warning", 0) or 0),
        )

    @classmethod
    def as_descriptor(cls):
        return ObjectField(cls)


class ServicePlanInfo(GraphModel):
    is_standalone = True

    applies_to = CharField(read_only=True)
    provisioning_status = CharField(read_only=True)
    id = CharField(read_only=True, graph_name="servicePlanId")
    name = CharField(read_only=True, graph_name="servicePlanName")

    @classmethod
    def as_descriptor(cls):
        return ObjectField(cls, many=True)


class SubscribedSku(GraphModel):
    # https://learn.microsoft.com/en-us/graph/api/subscribedsku-list?view=graph-rest-1.0&tabs=http
    endpoint = "/subscribedSkus"

    sku_id = CharField()  # skuId
    sku_part_number = CharField()  # skuPartNumber
    capability_status = CharField()  # capabilityStatus
    consumed_units = IntegerField()  # consumedUnits (int)
    applies_to = CharField()  # appliesTo (often "User")
    prepaid_units = LicenseUnitsDetail.as_descriptor()
    service_plans = ServicePlanInfo.as_descriptor()
