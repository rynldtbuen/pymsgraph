from collections.abc import Callable
from json import load
from pathlib import Path
from re import sub
from typing import Any, ClassVar
from pymsgraph.models.fields import CharField, IntegerField, ListField, ModelField
from pymsgraph.models.base import ReadOnlyModel, PropertyModel
from pymsgraph.models.query import QuerySet
from pymsgraph.utils import SimpleCache


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
    prepaid_units = ModelField(model_class=LicenseUnitsDetail)
    service_plans = ListField(ServicePlanInfo)

    PRODUCT_NAME_SKU_ID_MAP: ClassVar[dict[str, str]] = {}
    SKU_ID_PRODUCT_NAME_MAP: ClassVar[dict[str, str]] = {}
    SKU_PART_NUMBER_PRODUCT_NAME_MAP: ClassVar[dict[str, str]] = {}
    PRODUCT_NAMES_CSV_PATH: ClassVar[Path] = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "static"
        / "Product names and service plan identifiers for licensing.csv"
    )

    @property
    def product_name(self) -> str | None:
        return SubscribedSku.get_product_name(sku_id=self.sku_id)

    @property
    def available_units(self) -> int:
        if self.prepaid_units is None:
            return 0
        enabled = int(self.prepaid_units.enabled or 0)
        warning = int(self.prepaid_units.warning or 0)
        consumed = int(self.consumed_units or 0)
        return (enabled + warning) - consumed

    def has_available_units(self) -> bool:
        return self.available_units > 0

    def __repr__(self):
        return f"<SubscribedSku: {self.sku_id}>"

    @classmethod
    def _initialize_mapping(cls):
        csv_path = Path(cls.PRODUCT_NAMES_CSV_PATH)
        if not csv_path.is_file():
            return

        import csv

        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                display = (row.get("Product_Display_Name") or "").strip()
                guid = (row.get("GUID") or "").strip()
                if not display:
                    continue
                if guid:
                    cls.SKU_ID_PRODUCT_NAME_MAP.setdefault(guid.lower(), display)
                    cls.PRODUCT_NAME_SKU_ID_MAP.setdefault(
                        display.lower(), guid.lower()
                    )
                part_number = (row.get("Product_Sku") or "").strip()
                if part_number:
                    cls.SKU_PART_NUMBER_PRODUCT_NAME_MAP.setdefault(
                        part_number.lower(), display
                    )

    @classmethod
    def get_product_name(
        cls,
        *,
        sku_id: str | None = None,
        sku_part_number: str | None = None,
    ) -> str | None:

        if not cls.SKU_ID_PRODUCT_NAME_MAP:
            cls._initialize_mapping()
        if sku_id:
            key = sku_id.strip().lower()
            return cls.SKU_ID_PRODUCT_NAME_MAP.get(key)
        if sku_part_number:
            key = sku_part_number.strip().lower()
            return cls.SKU_PART_NUMBER_PRODUCT_NAME_MAP.get(key)
        raise ValueError("Provide sku_id or sku_part_number")

    @classmethod
    def get_sku_id(cls, product_name: str) -> str | None:
        if not product_name:
            return None
        if not cls.PRODUCT_NAME_SKU_ID_MAP:
            cls._initialize_mapping()
        key = " ".join(product_name.split()).lower()
        return cls.PRODUCT_NAME_SKU_ID_MAP.get(key)


class SubscribedSkuQuerySet(QuerySet[SubscribedSku]):
    model_class = SubscribedSku
    page_size = None

    @property
    def _cache(self) -> SimpleCache:
        async def _loader() -> dict[str, Any]:
            return {
                s.sku_id: s
                async for s in self._client.subscribed_skus
                if s.sku_id is not None
            }

        if self._client is not None and hasattr(self._client, "_subscribed_sku_cache"):
            return getattr(self._client, "_subscribed_sku_cache")

        cache = SimpleCache(loader=_loader)
        if self._client is not None:
            setattr(self._client, "_subscribed_sku_cache", cache)
        return cache
