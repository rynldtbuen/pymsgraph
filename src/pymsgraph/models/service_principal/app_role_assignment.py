from pymsgraph.fields import CharField, DateTimeField
from pymsgraph.models.base import Model
from pymsgraph.query import Capabilities, QuerySet


class AppRoleAssignment(Model):
    """
    Microsoft Graph appRoleAssignment resource (subset).

    https://learn.microsoft.com/en-us/graph/api/resources/approleassignment?view=graph-rest-1.0
    """

    is_read_only = True
    endpoint = "/appRoleAssignments"

    app_role_id = CharField()
    created_date_time = DateTimeField()
    principal_display_name = CharField()
    principal_id = CharField()
    principal_type = CharField()
    resource_display_name = CharField()
    resource_id = CharField()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"<AppRoleAssignment: {self.principal_display_name or self.principal_id}>"
        )


class AppRoleAssignmentQuerySet(QuerySet[AppRoleAssignment]):
    model_class = AppRoleAssignment
    capabilities = Capabilities.read_only(filter=True, get=True)
