from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pymsgraph.models.base import PropertyModel
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
    sharepoint_ids = ModelField(SharePointIds, read_only=True)

    # Navigation properties
    analytics = Field()
    document_set_versions = ListField()
    drive_item = Field()
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

    async def _get_path(self):
        p = self.path
        if p.startswith("/sites/"):
            c = self._client
            if "HOSTNAME" in p:
                hostname = await c.sites._get_hostname()
                p = p.replace("HOSTNAME", hostname)
            self._args = c, p, self._args[2]
        return p


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

    @property
    def path(self):
        if self.id is None and (p := self._args[1]) is not None:
            return p
        return super().path

    async def get(self) -> "List":
        p = self.path
        c = self._client
        if "HOSTNAME" in p:
            hostname = await c.sites._get_hostname()
            p = p.replace("HOSTNAME", hostname)
        data = await c.get(path=p)
        return List.from_graph(data=data, client=c, path=p)


class ListQuerySet(QuerySet[List]):
    model_class = List

    # @property
    # def path(self) -> str:
    #     p: str | None = self._args[1]
    #     if p is None:
    #         raise AttributeError(
    #             f"{type(self).__name__} object has no attribute 'path'"
    #         )
    #     if ":" in p:
    #         return p
    #     return super().path

    def by_name(self, name: str) -> "List":
        n = (name or "").strip()
        if not n:
            raise ValueError(f"{type(self).__name__} by_name requires a name.")
        n_encoded = quote(n, safe="")
        path = f"{self.path}/{n_encoded}"
        return List(client=self._client, path=path)


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
