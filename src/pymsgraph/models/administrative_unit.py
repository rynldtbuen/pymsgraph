from __future__ import annotations

from pymsgraph.models.directory_object import DirectoryObject

__all__ = ["AdministrativeUnit"]


class AdministrativeUnit(DirectoryObject):
    """
    Minimal administrative unit model.
    """

    endpoint = "/administrativeUnits"
