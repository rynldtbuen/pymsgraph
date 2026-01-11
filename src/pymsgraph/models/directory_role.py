from __future__ import annotations

from pymsgraph.models.directory_object import DirectoryObject

__all__ = ["DirectoryRole"]


class DirectoryRole(DirectoryObject):
    """
    Minimal directory role model.
    """

    endpoint = "/directoryRoles"
