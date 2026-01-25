from pymsgraph.models.query import QuerySet

from .common import AppRoleAssignment


class AppRoleAssignmentQuerySet(QuerySet[AppRoleAssignment]):
    model_class = AppRoleAssignment
