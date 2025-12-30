from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, TypeAlias, cast, override

from pymsgraph import utils
from pymsgraph.fields import CharField
from pymsgraph.models.base import Model
from pymsgraph.query import BulkQuerySet, Capabilities, QuerySet
from pymsgraph.models.subscribed_sku import ServicePlanInfo

if TYPE_CHECKING:
    from pymsgraph.models.user import User


class LicenseDetails(Model):
    """
    Graph licenseDetails  resource type.
    """

    is_read_only = True
    endpoint = "/licenseDetails"

    sku_id = CharField(read_only=True)
    sku_part_number = CharField(read_only=True)
    service_plans = ServicePlanInfo.as_descriptor()

    def __repr__(self):
        return f"<LicenseDetails: {self.sku_id}>"

    def _has_identity(self) -> bool:
        return False


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

    # def __iter__(self):
    #     if d := self._graph_data:

    def add(self, *args: arg_types) -> None:
        """
        Add license/s to this user.
        """

        objects: list[LicenseDetails] = list(
            utils.coerce_objects(*args, queryset=self, key="sku_id")
        )
        if not objects:
            return

        p = self._parent
        assert p is not None

        self._client.post(
            f"{p.endpoint}/assignLicense",
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

        objects: list[LicenseDetails] = list(
            utils.coerce_objects(*args, queryset=self, key="sku_id")
        )
        if not objects:
            return

        p = self._parent
        assert p is not None

        self._client.post(
            f"{p.endpoint}/assignLicense",
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

        client = self._client
        objects: list[LicenseDetails] = list(
            utils.coerce_objects(*args, queryset=LicensesQuerySet(), key="sku_id")
        )
        if not objects:
            return

        for users in utils.chunks(self._queryset.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for i, u in enumerate(users, start=1):
                u = cast(User, u)
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{u.endpoint}/assignLicense",
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
            utils.coerce_objects(*args, queryset=LicensesQuerySet(), key="sku_id")
        )
        if not objects:
            return

        client = self._client

        for users in utils.chunks(self._queryset.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for i, u in enumerate(users, start=1):
                u = cast("User", u)
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{u.endpoint}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "addLicenses": [],
                            "removeLicenses": [obj.sku_id for obj in objects],
                        },
                    }
                )

            batch_resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="remove user queryset licenses")
