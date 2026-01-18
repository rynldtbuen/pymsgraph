from pymsgraph.models.fields import BooleanField, CharField, Field
from pymsgraph.models.base import ReadOnlyModel
from pymsgraph.models.query import QuerySet


class ServicePrincipal(ReadOnlyModel):
    """
    Microsoft Graph servicePrincipal resource (subset).

    https://learn.microsoft.com/en-us/graph/api/resources/serviceprincipal?view=graph-rest-1.0
    """

    PATH = "/servicePrincipals"
    SEARCH_FIELD = "display_name"

    app_id = CharField()
    display_name = CharField()
    service_principal_type = CharField()
    account_enabled = BooleanField()
    app_owner_organization_id = CharField()
    app_role_assignment_required = BooleanField()

    tags = Field()
    app_roles = Field()
    oauth2_permission_scopes = Field()

    def __repr__(self) -> str:
        return f"<ServicePrincipal: {self.display_name or self.app_id}>"


class ServicePrincipalQuerySet(QuerySet[ServicePrincipal]):
    model_class = ServicePrincipal
