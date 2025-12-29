from pymsgraph.fields import BooleanField, CharField, Field
from pymsgraph.models.base import Model
from pymsgraph.query import Capabilities, QuerySet


class ServicePrincipal(Model):
    """
    Microsoft Graph servicePrincipal resource (subset).

    https://learn.microsoft.com/en-us/graph/api/resources/serviceprincipal?view=graph-rest-1.0
    """

    is_read_only = True
    endpoint = "/servicePrincipals"
    search_field = "display_name"

    app_id = CharField()
    display_name = CharField()
    service_principal_type = CharField()
    account_enabled = BooleanField()
    app_owner_organization_id = CharField()
    app_role_assignment_required = BooleanField()

    # Complex collections / objects
    tags = Field()
    app_roles = Field()
    oauth2_permission_scopes = Field()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<ServicePrincipal: {self.display_name or self.app_id}>"


class ServicePrincipalQuerySet(QuerySet[ServicePrincipal]):
    model_class = ServicePrincipal
    capabilities = Capabilities.read_only(filter=True, search=True, get=True)
