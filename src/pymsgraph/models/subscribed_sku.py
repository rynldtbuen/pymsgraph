from pathlib import Path
from typing import ClassVar
from pymsgraph.models.fields import CharField, IntegerField, ModelField
from pymsgraph.models.base import ReadOnlyModel, PropertyModel
from pymsgraph.models.query import QuerySet


class LicenseUnitsDetail(ReadOnlyModel, PropertyModel):
    """
    Graph licenseUnitsDetail resource type

    https://learn.microsoft.com/en-us/graph/api/resources/licenseunitsdetail?view=graph-rest-1.0
    """

    enabled = IntegerField()
    locked_out = IntegerField()
    suspended = IntegerField()
    warning = IntegerField()

    def __repr__(self):
        return f"<LicenseUnitsDetail: enabled={self.enabled}, locked_out={self.locked_out}, suspended={self.suspended}, warning={self.warning}>"


class ServicePlanInfo(ReadOnlyModel, PropertyModel):
    """
    Graph servicePlanInfo resource type

    https://learn.microsoft.com/en-us/graph/api/resources/serviceplaninfo?view=graph-rest-1.0
    """

    applies_to = CharField()
    provisioning_status = CharField()
    service_plan_id = CharField()
    service_plan_name = CharField()

    def __repr__(self):
        return f"<ServicePlanInfo: {self.service_plan_id}, {self.service_plan_name}>"


class SubscribedSku(ReadOnlyModel):
    """
    Graph subscribedSku resource type

    https://learn.microsoft.com/en-us/graph/api/subscribedsku-list?view=graph-rest-1.0&tabs=http
    """

    READ_ONLY = True
    PATH = "/subscribedSkus"

    account_name = CharField()
    account_id = CharField()
    sku_id = CharField()
    sku_part_number = CharField()
    capability_status = CharField()
    consumed_units = IntegerField()
    applies_to = CharField()
    prepaid_units = ModelField(LicenseUnitsDetail)
    service_plans = ModelField(ServicePlanInfo)

    PRODUCT_NAME_BY_SKU: ClassVar[dict[str, str]] = {}
    PRODUCT_NAMES_CSV_PATH: ClassVar[Path] = (
        Path(__file__).resolve().parents[3]
        / "static"
        / "Product names and service plan identifiers for licensing.csv"
    )

    @property
    def product_name(self) -> str | None:
        return SubscribedSku.get_product_name(sku_id=self.sku_id)

    def __repr__(self):
        return f"<SubscribedSku: {self.sku_id}>"

    @classmethod
    def get_product_name(
        cls,
        *,
        sku_id: str | None = None,
        sku_part_number: str | None = None,
    ) -> str | None:
        """
        Resolve a human-friendly product name for a SKU id or sku part number.

        Graph does not provide product names for subscribed SKUs, so this relies
        on a local mapping (PRODUCT_NAME_BY_SKU) that you can extend.
        """

        def _load():
            csv_path = Path(cls.PRODUCT_NAMES_CSV_PATH)
            if not csv_path.is_file():
                return

            import csv

            with csv_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    display = (row.get("Product_Display_Name") or "").strip()
                    guid = (row.get("GUID") or "").strip()
                    if not display:
                        continue
                    if guid:
                        cls.PRODUCT_NAME_BY_SKU.setdefault(guid.lower(), display)

        if not cls.PRODUCT_NAME_BY_SKU:
            _load()
        if not sku_id and not sku_part_number:
            raise ValueError("Provide sku_id or sku_part_number")
        if sku_id:
            key = sku_id.strip().lower()
            if key in cls.PRODUCT_NAME_BY_SKU:
                return cls.PRODUCT_NAME_BY_SKU[key]
        if sku_part_number:
            key = sku_part_number.strip().lower()
            return cls.PRODUCT_NAME_BY_SKU.get(key)
        return None


class SubscribedSkuQuerySet(QuerySet[SubscribedSku]):
    model_class = SubscribedSku
