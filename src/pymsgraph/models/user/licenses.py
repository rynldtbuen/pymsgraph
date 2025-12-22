from typing import TYPE_CHECKING, Any, ClassVar, Iterator

from pymsgraph import utils
from pymsgraph.fields import CharField
from pymsgraph.models.base import Model
from pymsgraph.models.subscribed_sku import ServicePlanInfo
from pymsgraph.query import Capabilities, QuerySet


if TYPE_CHECKING:
    from pymsgraph.models.user import User


class LicenseDetails(Model):
    capabilities: ClassVar[Capabilities] = Capabilities.read_only()

    sku_id = CharField(read_only=True)
    sku_part_number = CharField(read_only=True)
    service_plans = ServicePlanInfo.as_descriptor()


class UserLicensesQuerySet(QuerySet[LicenseDetails]):
    capabilities: ClassVar[Capabilities] = Capabilities.read_only()

    @classmethod
    def as_descriptor(cls) -> property:
        def fget(obj: "User", objtype=None) -> UserLicensesQuerySet:
            if obj is None:
                return cls  # type: ignore
            if obj.id is None:
                raise ValueError("User is not initialized or does not exist")
            qs = UserLicensesQuerySet(
                client=obj.client,
                model=LicenseDetails,
                endpoint=f"{obj.endpoint}/licenseDetails",
            )
            qs._user = obj  # type: ignore[attr-defined]
            return qs

        return property(fget=fget)

    def _iter_objects(self, data: dict[str, Any]) -> Iterator[LicenseDetails]:
        for item in data.get("value", []):
            yield self._model(graph_data=item, qs=self)

    def _assign_payload(self, *, add: list[str], remove: list[str]) -> dict[str, Any]:
        return {
            "addLicenses": [{"skuId": sid, "disabledPlans": []} for sid in add],
            "removeLicenses": remove,
        }

    def add(self, *licenses: Any) -> None:
        user = getattr(self, "_user", None)
        if not user:
            raise ValueError("User is not configured for this queryset")

        sku_ids = utils.coerce_values(*licenses, attr_names=("sku_id", "id"))
        if not sku_ids:
            return

        client = self._client
        resp = client.post(
            "/$batch",
            json_body={
                "requests": [
                    {
                        "id": "1",
                        "method": "POST",
                        "url": f"{user.endpoint}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": self._assign_payload(add=sku_ids, remove=[]),
                    }
                ]
            },
        )
        utils.raise_batch_errors(resp, action="add licenses")

    def remove(self, *licenses: Any) -> None:
        user = getattr(self, "_user", None)
        if not user:
            raise ValueError("User is not configured for this queryset")

        sku_ids = utils.coerce_values(*licenses, attr_names=("sku_id", "id"))
        if not sku_ids:
            return

        client = self._client
        resp = client.post(
            "/$batch",
            json_body={
                "requests": [
                    {
                        "id": "1",
                        "method": "POST",
                        "url": f"{user.endpoint}/assignLicense",
                        "headers": {"Content-Type": "application/json"},
                        "body": self._assign_payload(add=[], remove=sku_ids),
                    }
                ]
            },
        )
        utils.raise_batch_errors(resp, action="remove licenses")
