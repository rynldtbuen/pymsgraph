from typing import Any

from pymsgraph.fields import CharField
from .resources import MultiValuedResource, SingleValuedResource


class ServicePrincipals(MultiValuedResource["ServicePrincipal"]):

    ITEM_CLASS = "ServicePrincipal"

    @property
    def relative_endpoint(self):
        return "servicePrincipals"

    def by_service_principal_id(self, service_principal_id: str):
        return ServicePrincipal(
            self._client, parent=self, service_principal_id=service_principal_id
        )


class ServicePrincipal(SingleValuedResource):

    id = CharField

    @property
    def relative_url(self) -> str:
        return f"/{self._service_principal_id}"

    @property
    def app_role_assigned_to(self) -> "AppRoleAssignedTo":
        return AppRoleAssignedTo(self._client, parent=self)

    def _set_kwargs(self, kwargs: dict[str, Any] | dict = {}):
        service_principal_id = kwargs.get("service_principal_id") or self.id
        if service_principal_id is None:
            raise ValueError("Argument is required, 'service_principal_id'")
        self._service_principal_id = service_principal_id


class AppRoleAssignedTo(MultiValuedResource["AppRoleAssignedToDetail"]):

    FILTER = False
    ORDERBY = False
    TOP = False
    COUNT = False
    SELECT = False
    EXPAND = False

    ITEM_CLASS = "AppRoleAssignedToDetail"

    @property
    def relative_url(self):
        return f"/appRoleAssignedTo"


class AppRoleAssignedToDetail(SingleValuedResource):

    SELECT = False
    EXPAND = False
    GET = False

    # @property
    # def relative_endpoint(self):
    #     return self._parent.relative_endpoint
