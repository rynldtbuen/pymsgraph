from __future__ import annotations

from pymsgraph.models.directory_object import DirectoryObject


class AdministrativeUnit(DirectoryObject):
    """
    Graph administrativeUnit resource type

    https://learn.microsoft.com/en-us/graph/api/resources/administrativeunit?view=graph-rest-1.0
    """

    endpoint = "/administrativeUnits"
