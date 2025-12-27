from __future__ import annotations

from pymsgraph.fields import CharField
from pymsgraph.models.base import Model
from pymsgraph.query import Capabilities, QuerySet

__all__ = ["List", "ListQuerySet"]


class List(Model):
    """
    Graoh SharePoint list resource (subset of fields).
    """

    display_name = CharField(read_only=True)
    name = CharField(read_only=True)
    description = CharField(read_only=True)
    web_url = CharField(read_only=True)

    is_read_only = True

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<List: {self.display_name or self.name}>"


class ListQuerySet(QuerySet[List]):
    model_class = List
    capabilities = Capabilities.read_only()
