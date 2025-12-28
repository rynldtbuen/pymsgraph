from __future__ import annotations

from typing import Any
from xml.dom.minidom import Attr

from pymsgraph.fields import CharField, DateTimeField
from pymsgraph.models.base import Model
from pymsgraph.query import Capabilities, QuerySet

__all__ = [
    "List",
    "ListQuerySet",
    "ListItem",
    "ListItemsQuerySet",
    "FieldValueSet",
]


class List(Model):
    """
    Graph SharePoint list resource (subset of fields).
    """

    is_read_only = True
    endpoint = "/lists"

    display_name = CharField(read_only=True)
    name = CharField(read_only=True)
    description = CharField(read_only=True)
    web_url = CharField(read_only=True)
    created_date_time = DateTimeField(read_only=True)
    last_modified_date_time = DateTimeField(read_only=True)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<List: {self.display_name or self.name}>"

    @property
    def items(self) -> ListItemsQuerySet:
        return ListItemsQuerySet(parent=self)


class ListQuerySet(QuerySet[List]):
    model_class = List
    capabilities = Capabilities.read_only(filter=True)


class ListItem(Model):
    endpoint = "/items"

    display_name = CharField(read_only=True)
    name = CharField(read_only=True)
    description = CharField(read_only=True)
    web_url = CharField(read_only=True)
    created_date_time = DateTimeField(read_only=True)
    last_modified_date_time = DateTimeField(read_only=True)

    @property
    def fields(self) -> FieldValueSet:
        try:
            return getattr(self, "_fields")
        except AttributeError:
            fields = FieldValueSet(
                parent=self, graph_data=self._graph_data.get("fields")
            )
            setattr(self, "_fields", fields)
            return fields


class ListItemsQuerySet(QuerySet[ListItem]):
    model_class = ListItem
    capabilities = Capabilities.read_write()

    def create(self, *, fields: dict[str, Any], **kwargs: Any) -> ListItem:
        """
        Create a list item. `fields` must be provided as a dict of field values.
        """
        if not fields:
            raise ValueError("ListItemsQuerySet.create requires field values")

        data = self._client.post(
            self.endpoint, json_body={"fields": fields}, headers=self._headers
        )
        return self.model_class(graph_data=data, parent=self)


class FieldValueSet(Model):
    endpoint = "/fields"

    def __getitem__(self, key: str) -> Any:
        return self._graph_data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if self._graph_data.get(key) == value:
            return
        self._graph_data[key] = value
        self._dirty.add(key)

    def save(self) -> bool:
        if not self._dirty:
            return False
        payload = {k: self._graph_data[k] for k in self._dirty}
        self._client.patch(self.endpoint, json_body=payload)
        self._dirty.clear()
        return True

    def _has_identity(self) -> bool:
        return False
