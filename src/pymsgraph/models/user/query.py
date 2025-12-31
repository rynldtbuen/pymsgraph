import csv
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias, cast

from pymsgraph import utils
from pymsgraph.fields import CharField, Field
from pymsgraph.models.base import Model
from pymsgraph.models.subscribed_sku import SubscribedSku
from pymsgraph.query import BulkQuerySet, Capabilities, QuerySet

if TYPE_CHECKING:
    from pymsgraph.models.group import Group
    from pymsgraph.models.user import User


# class LicenseDetails(Model):
#     """
#     Graph licenseDetails resource type.
#     """

#     is_read_only = True
#     endpoint = "/licenseDetails"

#     sku_id = CharField()
#     sku_part_number = CharField()
#     service_plans = ServicePlanInfo.as_descriptor()

#     def __repr__(self):
#         return f"<LicenseDetails: {self.product_name}>"

#     def _has_identity(self) -> bool:
#         return False

#     @property
#     def product_name(self):
#         return SubscribedSku.get_product_name(sku_id=self.sku_id)


assigned_license_arg_types: TypeAlias = (
    """
    str
    | AssignedLicense
    | Iterable[str]
    | Iterable[AssignedLicense]
    | QuerySet[AssignedLicense]
    """
)


class AssignedLicense(Model):
    """
    Graph assignedLicense resource type.
    """

    is_read_only = True
    endpoint = "/assignedLicense"

    īd = CharField(graph_name="skuId")
    disabledPlans = Field()

    @property
    def product_name(self):
        return SubscribedSku.get_product_name(sku_id=self.id)


class AssignedLicenseQuerySet(QuerySet["AssignedLicense"]):
    """
    User's licenses

    Usage:
        User.licenses
        User.licenses.add(...)
        User.licenses.remove(...)
    """

    model_class = AssignedLicense
    capabilities = Capabilities.read_only(filter=True)

    def add(self, *args: assigned_license_arg_types) -> None:
        """
        Add license/s to this user.
        """

        objects = list(utils.coerce_objects(*args, queryset=self))
        if not objects:
            return

        p = self._parent
        assert p is not None

        self._client.post(
            f"{p.endpoint}/assignLicense",
            json_body={
                "addLicenses": [
                    {"skuId": obj.id, "disabledPlans": []} for obj in objects
                ],
                "removeLicenses": [],
            },
        )

    def remove(self, *args: assigned_license_arg_types) -> None:
        """
        Remove license/s from this user.
        """

        objects = list(utils.coerce_objects(*args, queryset=self))
        if not objects:
            return

        p = self._parent
        assert p is not None

        self._client.post(
            f"{p.endpoint}/assignLicense",
            json_body={
                "addLicenses": [],
                "removeLicenses": [obj.id for obj in objects],
            },
        )

    @classmethod
    def _collection_any_lookup(cls, lookup: str, value: str) -> str:
        func = utils.collection_any_lookup(
            field_name="assigned_licenses", element_field=True, var="u"
        )
        return func(lookup, value)


class LicensesBulkQuerySet(BulkQuerySet):
    """
    User queryset's licenses.

    Usage:
        UserQuerySet.filter(...).licenses.add(...)
        UserQuerySet.filter(...).licenses.remove(...)
    """

    def add(self, *args: assigned_license_arg_types) -> None:
        """
        Add licenses to all users in this queryset.
        """

        client = self._client
        objects = list(utils.coerce_objects(*args, queryset=AssignedLicenseQuerySet()))
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
                                {"skuId": obj.id, "disabledPlans": []}
                                for obj in objects
                            ],
                            "removeLicenses": [],
                        },
                    }
                )

            batch_resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="add user queryset licenses")

    def remove(self, *args: assigned_license_arg_types) -> None:
        """
        Remove license/s from all users in this queryset.
        """

        objects = list(utils.coerce_objects(*args, queryset=AssignedLicenseQuerySet()))
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
                            "removeLicenses": [obj.id for obj in objects],
                        },
                    }
                )

            batch_resp = client.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(batch_resp, action="remove user queryset licenses")

    def to_csv(self, path: str | Path) -> None:
        """
        Export user licenses to CSV.

        Headers: id, display_name, user_principal, mail, sku_id, sku_part_number, product_name
        """
        out_path = Path(path)
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "id",
                    "display_name",
                    "user_principal",
                    "mail",
                    "sku_id",
                    "sku_part_number",
                    "product_name",
                ]
            )
            for user in self._queryset.all():
                user_id = getattr(user, "id", None)
                display_name = getattr(user, "display_name", None)
                upn = getattr(user, "user_principal_name", None)
                mail = getattr(user, "mail", None)
                licenses = list(user.licenses)
                if not licenses:
                    writer.writerow([user_id, display_name, upn, mail, "", "", ""])
                    continue
                for lic in licenses:
                    product_name = SubscribedSku.get_product_name(sku_id=lic.sku_id)
                    writer.writerow(
                        [
                            user_id,
                            display_name,
                            upn,
                            mail,
                            lic.sku_id,
                            lic.sku_part_number,
                            product_name or "",
                        ]
                    )


group_arg_types: TypeAlias = (
    "str | Group | Iterable[str] | Iterable[Group] | QuerySet[Group]"
)


class MemberOfQuerySet(QuerySet["Group"]):
    """
    User's member of queryset.

    Usage:
        User.member_of
        User.member_of.add(...)
        User.member_of.remove(...)
    """

    model_class = "Group"  # type: ignore
    endpoint = "/memberOf"
    capabilities = Capabilities.read_only(filter=True, search=True, count=True)

    def add(self, *args: group_arg_types) -> None:
        """
        Add group/s to this user.
        """

        c = self._client
        u: "User" = getattr(self, "_parent")
        objects = utils.coerce_objects(*args, queryset=c.groups)

        for groups in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for i, g in enumerate(groups, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "POST",
                        "url": f"{g.members.endpoint}/$ref",
                        "headers": {"Content-Type": "application/json"},
                        "body": {"@odata.id": f"{c.base_url}/directoryObjects/{u.id}"},
                    }
                )
            resp = c.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="add user to groups")

    def remove(self, *args: group_arg_types) -> None:
        """
        Remove group/s from this user.
        """

        c = self._client
        u: User = getattr(self, "_parent")
        objects = utils.coerce_objects(*args, queryset=c.groups)

        for groups in utils.chunks(objects, 20):
            requests: list[dict[str, Any]] = []
            for i, g in enumerate(groups, start=1):
                requests.append(
                    {
                        "id": str(i),
                        "method": "DELETE",
                        "url": f"{g.members.endpoint}/{u.id}/$ref",
                    }
                )
            resp = c.post("/$batch", json_body={"requests": requests})
            utils.raise_batch_errors(resp, action="remove user from groups")

    def _iter_objects(self, data: dict[str, Any]) -> Iterator["Group"]:
        for item in data.get("value", []):
            otype = item.get("@odata.type")
            if otype and otype.lower() != "#microsoft.graph.group":
                continue
            yield self.model_class(graph_data=item, qs=self)


class MemberOfBulkQuerySet(BulkQuerySet):
    """
    User queryset's member of.

    Usage:
        UserQuerySet.filter(...).member_of.add(...)
        UserQuerySet.filter(...).member_of.remove(...)
    """

    def add(self, *args: group_arg_types) -> None:
        """
        Add group/s to users in this queryset.
        """

        c = self._client
        objects = utils.coerce_objects(*args, queryset=c.groups)

        for group in objects:
            for users in utils.chunks(self._queryset.select("id"), 20):
                binds = [f"{c.base_url}/directoryObjects/{u.id}" for u in users]
                c.patch(
                    group.endpoint,
                    json_body={"members@odata.bind": binds},
                )

    def remove(self, *args: group_arg_types) -> None:
        """
        Remove group/s from users in this queryset.
        """
        c = self._client
        objects = utils.coerce_objects(*args, queryset=c.groups)

        for group in objects:
            for users in utils.chunks(self._queryset.select("id"), 20):
                requests: list[dict[str, Any]] = []
                for i, u in enumerate(users, start=1):
                    requests.append(
                        {
                            "id": str(i),
                            "method": "DELETE",
                            "url": f"{group.members.endpoint}/{u.id}/$ref",
                        }
                    )
                batch_resp = c.post("/$batch", json_body={"requests": requests})
                utils.raise_batch_errors(
                    batch_resp, action="remove users in queryset from groups"
                )
