from typing import TYPE_CHECKING
import httpx
import pytest

from pymsgraph.models.subscribed_sku import (
    LicenseUnitsDetail,
    ServicePlanInfo,
    SubscribedSku,
)

if TYPE_CHECKING:
    from tests.conftest import MakeClient


@pytest.mark.asyncio
async def test_qs(make_client: "MakeClient"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/subscribedSkus":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "sku1",
                            "accountName": "Contoso",
                            "accountId": "acc1",
                            "skuId": "sku-id-1",
                            "skuPartNumber": "PART1",
                            "capabilityStatus": "Enabled",
                            "consumedUnits": 5,
                            "appliesTo": "User",
                            "prepaidUnits": {
                                "enabled": 25,
                                "lockedOut": 0,
                                "suspended": 0,
                                "warning": 0,
                            },
                            "servicePlans": [
                                {
                                    "servicePlanId": "sp1",
                                    "servicePlanName": "Plan1",
                                    "appliesTo": "User",
                                    "provisioningStatus": "Success",
                                }
                            ],
                        }
                    ]
                },
            )
        return httpx.Response(404)

    c, _ = make_client(handler)

    skus = [obj async for obj in c.subscribed_skus]

    assert len(skus) == 1
    sku = skus[0]
    assert isinstance(sku, SubscribedSku)
    assert sku.account_name == "Contoso"
    assert sku.sku_id == "sku-id-1"
    assert sku.prepaid_units.enabled == 25
    assert isinstance(sku.prepaid_units, LicenseUnitsDetail)
    assert isinstance(sku.service_plans[0], ServicePlanInfo)
    assert sku.service_plans[0].service_plan_name == "Plan1"


def test_subscribed_sku_product_name_from_csv(tmp_path):
    from pymsgraph.models.subscribed_sku import SubscribedSku

    csv_path = tmp_path / "Product names and service plan identifiers for licensing.csv"
    csv_path.write_text(
        "Product_Display_Name,String_Id,GUID,Service_Plan_Name,Service_Plan_Id,Service_Plans_Included_Friendly_Names\n"
        "Microsoft Business Premium,O365_BUSINESS_PREMIUM,abc123-0000-0000-0000-000000000000,PlanA,sp1,Plan A\n",
        encoding="utf-8",
    )

    # reset mapping and point loader to temp CSV
    SubscribedSku.PRODUCT_NAME_SKU_ID_MAP.clear()
    SubscribedSku.PRODUCT_NAMES_CSV_PATH = csv_path

    name = SubscribedSku.get_product_name(sku_id="abc123-0000-0000-0000-000000000000")
    assert name == "Microsoft Business Premium"
    # SubscribedSku.PRODUCT_NAMES_CSV_PATH = None
