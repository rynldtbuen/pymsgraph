from collections.abc import Iterable
from typing import Any, ClassVar, TypeAlias

from pymsgraph import utils
from pymsgraph.fields import CharField
from pymsgraph.models.base import Model
from pymsgraph.query import BulkQuerySet, Capabilities, QuerySet
from pymsgraph.models.subscribed_sku import ServicePlanInfo


class LicenseDetails(Model):
    """
    Graph licenseDetails  resource type.
    """

    is_read_only = True

    sku_id = CharField(read_only=True)
    sku_part_number = CharField(read_only=True)
    service_plans = ServicePlanInfo.as_descriptor()

    def __repr__(self):
        return f"<LicenseDetails: {self.sku_id}>"


arg_types: TypeAlias = (
    str
    | LicenseDetails
    | Iterable[str]
    | Iterable[LicenseDetails]
    | QuerySet["LicenseDetails"]
)


class LicensesQuerySet(QuerySet["LicenseDetails"]):
    """
    User's licenses

    Usage:
        User.licenses
        User.licenses.add(...)
        User.licenses.remove(...)
    """

    model_class = LicenseDetails
    capabilities = Capabilities.read_only()

    def add(self, *args: arg_types) -> None:
        """
        Add license/s to this user.
        """

        user = self._get_object()
        objects: list[LicenseDetails] = list(
            utils.coerce_objects(*args, model_class=self.model_class, key="sku_id")
        )
        if not objects:
            return

        self._client.post(
            f"{user.endpoint}/assignLicense",
            json_body={
                "addLicenses": [
                    {"skuId": obj.sku_id, "disabledPlans": []} for obj in objects
                ],
                "removeLicenses": [],
            },
        )

    def remove(self, *args: arg_types) -> None:
        """
        Remove license/s from this user.
        """

        user = self._get_object()
        objects: list[LicenseDetails] = list(
            utils.coerce_objects(*args, model_class=self.model_class, key="sku_id")
        )
        if not objects:
            return

        self._client.post(
            f"{user.endpoint}/assignLicense",
            json_body={
                "addLicenses": [],
                "removeLicenses": [obj.sku_id for obj in objects],
            },
        )


class LicensesBulkQuerySet(BulkQuerySet):
    """
    User queryset's licenses.

    Usage:
        UserQuerySet.filter(...).groups.add(...)
        UserQuerySet.filter(...).groups.remove(...)
    """

    def add(self, *args: arg_types) -> None:
        """
        Add licenses to all users in this queryset.
        """

        objects: list[LicenseDetails] = list(
            utils.coerce_objects(*args, model_class=LicenseDetails, key="sku_id")
        )
        if not objects:
            return

        client = self._client

        for users in utils.chunks(self._qs.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for index, user in enumerate(users, start=1):
                requests.append(
                    {
                        "id": str(index),
                        "method": "POST",
                        "url": f"{user.endpoint}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "addLicenses": [
                                {"skuId": obj.sku_id, "disabledPlans": []}
                                for obj in objects
                            ],
                            "removeLicenses": [],
                        },
                    }
                )

            batch_resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="add user queryset licenses")

    def remove(self, *args: arg_types) -> None:
        """
        Remove license/s from all users in this queryset.
        """

        objects: list[LicenseDetails] = list(
            utils.coerce_objects(*args, model_class=LicenseDetails, key="sku_id")
        )
        if not objects:
            return

        client = self._client

        for users in utils.chunks(self._qs.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for index, user in enumerate(users, start=1):
                requests.append(
                    {
                        "id": str(index),
                        "method": "POST",
                        "url": f"{user.endpoint}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "addLicenses": [],
                            "removeLicenses": [obj.sku_id for obj in objects],
                        },
                    }
                )

            batch_resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="remove user queryset licenses")
