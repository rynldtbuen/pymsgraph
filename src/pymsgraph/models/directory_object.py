from __future__ import annotations

from pymsgraph.models.base import Model

__all__ = ["DirectoryObject"]


class DirectoryObject(Model):
    """
    Minimal base model for directory objects.
    """

    endpoint = "/directoryObjects"
