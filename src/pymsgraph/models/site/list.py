from __future__ import annotations

from typing import Any

from pymsgraph.models.base import Model, PropertyModel
from pymsgraph.models.common import BaseItem, SharePointIds
from pymsgraph.models.fields import (
    CharField,
    Field,
    ListField,
    ModelField,
    QuerySetField,
)
from pymsgraph.models.query import QuerySet


class ListItem(BaseItem):
    """
    Graph listItem resource.

    https://learn.microsoft.com/en-us/graph/api/resources/listItem
    """

    PATH = "/items"

    content_type = Field()
    sharepoint_ids = ModelField(SharePointIds)

    # Navigation properties
    analytics = Field()
    document_set_versions = ListField()
    drive_item = Field()
    # fields = ModelField()
    versions = ListField()

    @property
    def fields(self) -> FieldValueSet:
        try:
            return getattr(self, "_fields")
        except AttributeError:
            fields = FieldValueSet.from_graph(
                data=self._graph_data.get("fields", {}),
                client=self._args[0],
                path=self.path,
            )
            setattr(self, "_fields", fields)
            return fields


class ListItemsQuerySet(QuerySet[ListItem]):
    model_class = ListItem

    async def create(self, **kwargs: Any) -> ListItem:
        """
        Create a list item. `fields` must be provided as a dict of field values.
        """
        if (fields := kwargs.get("fields")) is None:
            raise ValueError("ListItemsQuerySet.create requires field values")

        data = await self._client.post(
            self.path, body={"fields": fields}, headers=self._headers
        )
        return self.make_from_graph(data)


class List(BaseItem):
    """
    Graph list resource.

    https://learn.microsoft.com/en-us/graph/api/resources/list
    """

    PATH = "/lists"

    display_name = CharField()
    list = Field()
    sharepoint_ids = ModelField(SharePointIds)
    system = Field()

    # Navigation properties
    columns = ListField()
    content_types = ListField()
    drive = Field()
    items = QuerySetField(ListItemsQuerySet)
    operations = ListField()
    subscriptions = ListField()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<List: {self.display_name or self.name}>"

    # @property
    # def items(self) -> ListItemsQuerySet:
    #     return ListItemsQuerySet(self._client, path=f"{self.path}/items")


class ListQuerySet(QuerySet[List]):
    model_class = List


class FieldValueSet(PropertyModel):
    PATH = "/fields"

    def __getitem__(self, key: str) -> Any:
        return self._graph_data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if self._graph_data.get(key) == value:
            return
        self._graph_data[key] = value
        self._dirty.add(key)

    async def update(self, data: dict[str, Any] | None = None) -> bool:
        if data is not None:
            graph_data = self._graph_data
            for k, v in data.items():
                try:
                    self._graph_data[k]
                except KeyError:
                    continue
                graph_data[k] = v
                self._dirty.add(k)

        if not self._dirty:
            return False
        payload = {k: self._graph_data[k] for k in self._dirty}
        await self._client.patch(self.path, body=payload)
        self._dirty.clear()
        return True
