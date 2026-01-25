from pymsgraph.models.fields import CharField, DateTimeField
from pymsgraph.models.base import ReadOnlyModel
from pymsgraph.models.query import QuerySet


class AppRoleAssignment(ReadOnlyModel):
    """
    Microsoft Graph appRoleAssignment resource (subset).

    https://learn.microsoft.com/en-us/graph/api/resources/approleassignment?view=graph-rest-1.0
    """

    PATH = "/appRoleAssignments"

    app_role_id = CharField()
    created_date_time = DateTimeField()
    principal_display_name = CharField()
    principal_id = CharField()
    principal_type = CharField()
    resource_display_name = CharField()
    resource_id = CharField()

    def __repr__(self) -> str:
        return f"<AppRoleAssignment: {self.resource_display_name}, {self.principal_display_name}>"
