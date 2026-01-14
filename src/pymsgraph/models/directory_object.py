from __future__ import annotations

from pymsgraph.models.base import Model
from pymsgraph.models.fields import CharField


class DirectoryObject(Model):
    """
    Graph directoryObject resource type

    https://learn.microsoft.com/en-us/graph/api/resources/directoryobject?view=graph-rest-1.0
    """

    PATH = "/directoryObjects"
