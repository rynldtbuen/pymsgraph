from __future__ import annotations

from typing import Any, overload
from urllib.parse import quote

from pymsgraph import utils
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
    DEFAULT_EXPAND_FIELDS: tuple[str, ...] | None = ("fields",)
    READ_ONLY = False

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
        fields = kwargs.get("fields")
        if not isinstance(fields, dict):
            raise ValueError(
                f"ListItemsQuerySet.create expected a dict object, got '{fields}'"
            )
        path = await self._get_path()
        data = await self._client.post(
            path, body={"fields": fields}, headers=self._headers
        )
        return self.make_from_graph(data)

    async def create_many(self, *items: dict[str, Any]) -> "ListItemsQuerySet":
        """
        Create list items in batches via $batch.
        Each item should be a dict of field values or a payload with a 'fields' dict.
        """
        items_list = list(items)
        if not items_list:
            return self

        path = await self._get_path()
        created: list[ListItem] = []
        headers = {"Content-Type": "application/json"}
        if self._headers:
            headers.update(self._headers)

        for chunked_items in utils.chunks(items_list, 20):
            requests: list[dict[str, Any]] = []
            response_order: list[str] = []

            for i, item in enumerate(chunked_items, start=1):
                if not isinstance(item, dict):
                    raise TypeError("ListItemsQuerySet.create_many expects dict items")
                if "fields" in item:
                    fields = item.get("fields")
                    if not isinstance(fields, dict):
                        raise ValueError(
                            "ListItemsQuerySet.create_many requires 'fields' to be a dict"
                        )
                    body = item
                else:
                    body = {"fields": item}

                request_id = str(i)
                requests.append(
                    {
                        "id": request_id,
                        "method": "POST",
                        "url": path,
                        "headers": headers,
                        "body": body,
                    }
                )
                response_order.append(request_id)
            batch_resp = await self._client.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(batch_resp, requests, action="create list items")

            responses = {
                str(r.get("id")): r for r in batch_resp.get("responses", []) or []
            }
            for request_id in response_order:
                resp = responses.get(request_id)
                if not resp:
                    continue
                body = resp.get("body") or {}
                if body:
                    created.append(self.make_from_graph(body))

        return self.with_objects(*created)

    async def update(self, **fields: Any) -> int:
        """
        Update fields for all list items in this queryset using $batch.
        If no fields are provided, updates per-item dirty fields cached on objects.
        """
        if self._model_class.READ_ONLY:
            raise ValueError(f"{self._model_class.__name__} is read-only")

        headers = {"Content-Type": "application/json"}
        # if self._headers:
        #     headers.update(self._headers)

        if fields:
            if (
                len(fields) == 1
                and "fields" in fields
                and isinstance(fields["fields"], dict)
            ):
                payload = fields["fields"]
            else:
                payload = fields

            if not payload:
                return 0

            total_updated = 0
            async for chunked_items in utils.achunks(self.select("id"), 20):
                requests: list[dict[str, Any]] = []
                for i, item in enumerate(chunked_items, start=1):
                    if not getattr(item, "id", None):
                        continue
                    requests.append(
                        {
                            "id": str(i),
                            "method": "PATCH",
                            "url": f"{item.path}/fields",
                            "headers": headers,
                            "body": payload,
                        }
                    )
                if not requests:
                    continue
                batch_resp = await self._client.post(
                    "/$batch", body={"requests": requests}
                )
                utils.raise_batch_errors(
                    batch_resp, requests, action="update list item fields"
                )
                total_updated += len(requests)

            return total_updated

        # No explicit fields provided; use dirty fields on cached objects.
        items: list[ListItem] = []
        if self._seeded_objects is not None:
            items = list(self._seeded_objects)
        elif self._paginator is not None:
            cached = self._paginator._cached_objects
            for page_items in cached.values():
                items.extend(page_items)

        if not items:
            return 0

        total_updated = 0
        seen_ids: set[str] = set()
        for chunked_items in utils.chunks(items, 20):
            requests: list[dict[str, Any]] = []
            field_value_sets: list[Any] = []

            for i, item in enumerate(chunked_items, start=1):
                item_id = getattr(item, "id", None)
                if not item_id or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                field_value_set = item.fields
                graph_data = field_value_set._graph_data
                payload = {k: graph_data.get(k) for k in field_value_set._dirty}
                if not payload:
                    continue
                requests.append(
                    {
                        "id": str(i),
                        "method": "PATCH",
                        "url": f"{item.path}/fields",
                        "headers": headers,
                        "body": payload,
                    }
                )
                field_value_sets.append(field_value_set)

            if not requests:
                continue
            batch_resp = await self._client.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(
                batch_resp,
                requests,
                action="update list item fields (dirty)",
            )
            for field_value_set in field_value_sets:
                field_value_set._dirty.clear()
            total_updated += len(requests)

        return total_updated

    async def delete(self, force: bool = False) -> int:
        """
        Delete all list items in this queryset using $batch.
        """
        if not force:
            raise RuntimeError("Set 'force=True' to proceed.")

        deleted = 0
        async for chunked_items in utils.achunks(self.select("id"), 20):
            requests: list[dict[str, Any]] = []
            for i, item in enumerate(chunked_items, start=1):
                if not getattr(item, "id", None):
                    continue
                requests.append(
                    {
                        "id": str(i),
                        "method": "DELETE",
                        "url": item.path,
                    }
                )
            if not requests:
                continue
            batch_resp = await self._client.post("/$batch", body={"requests": requests})
            utils.raise_batch_errors(batch_resp, requests, action="delete list items")
            deleted += len(requests)
        return deleted

    async def _get_path(self):
        p = self.path
        if p.startswith("/sites/"):
            c = self._client
            if "HOSTNAME" in p:
                hostname = await c.sites._get_hostname()
                p = p.replace("HOSTNAME", hostname)
            parent_list = self._kwargs.get("obj")
            if (
                "/lists/" in p
                and "/items" in p
                and not getattr(self, "_list_id_resolved", False)
                and not getattr(parent_list, "id", None)
            ):
                list_path = p.split("/items", 1)[0]
                list_data = await c.get(path=list_path)
                if (list_id := list_data.get("id")) is not None:
                    base = f"{list_path.rsplit('/', 1)[0]}/{list_id}"
                    if base != list_path:
                        p = f"{base}{p[len(list_path):]}"
                setattr(self, "_list_id_resolved", True)
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
        if data.get("id") and p.rsplit("/", 1)[-1] != "lists":
            p = p.rsplit("/", 1)[0]
        return List.from_graph(data=data, client=c, path=p)


class ListQuerySet(QuerySet[List]):
    model_class = List

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
