from __future__ import annotations

from pymsgraph.models.directory_object import DirectoryObject


class DirectoryRole(DirectoryObject):
    """
    Graph directoryRole resource type.

    https://learn.microsoft.com/en-us/graph/api/resources/directoryrole?view=graph-rest-1.0
    """

    endpoint = "/directoryRoles"
