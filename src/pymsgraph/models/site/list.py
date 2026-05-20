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
        """
        Return mutable list item field values (`/items/{id}/fields`).

        Returns:
            FieldValueSet:
                Wrapper around the item's field payload that tracks dirty keys
                for partial updates.

        Notes:
            The wrapper is lazily created and cached on first access.
        """
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
    """
    QuerySet for SharePoint list items (`/lists/{id}/items`).

    Provides create/bulk-create/bulk-update/bulk-delete helpers with Graph
    batching where applicable.
    """

    model_class = ListItem

    async def create(self, **kwargs: Any) -> ListItem:
        """
        Create a single list item.

        Args:
            **kwargs:
                Must include `fields` as `dict[str, Any]`.

        Returns:
            ListItem:
                Created list item model.

        Raises:
            ValueError:
                If `fields` is missing or not a dictionary.
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.

        Example:
            ```python
            item = await list_obj.items.create(
                fields={"Title": "Quarterly Report", "Status": "Draft"}
            )
            ```
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
        Create many list items using Graph `$batch`.

        Args:
            *items:
                Each item can be:
                - a plain fields dictionary (wrapped as `{"fields": ...}`)
                - a payload containing a `fields` dictionary

        Returns:
            ListItemsQuerySet:
                Seeded queryset containing created list item objects.

        Raises:
            TypeError:
                If any item is not a dictionary.
            ValueError:
                If an item payload includes non-dict `fields`.
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.
            RuntimeError:
                If any batch item fails (`utils.raise_batch_errors`).

        Notes:
            Requests are sent in chunks of up to 20 operations per batch.
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
        Update list item fields for all items in this queryset.

        Args:
            **fields:
                Update payload. Two supported modes:
                - explicit mode: pass field key/values (or `fields={...}`)
                - dirty mode: pass nothing to persist tracked `item.fields` changes
                  from cached/seeded objects

        Returns:
            int:
                Number of updated items.

        Raises:
            ValueError:
                If model is read-only.
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.
            RuntimeError:
                If any batch item fails (`utils.raise_batch_errors`).

        Notes:
            - Updates are sent via `$batch` in chunks of up to 20 items.
            - In dirty mode, only tracked keys from `FieldValueSet._dirty` are sent.
            - Dirty markers are cleared only after successful batch update.

        Example:
            ```python
            # Explicit bulk update
            count = await list_obj.items.filter(...).update(Status="Archived")

            # Dirty-mode update from cached object(s)
            item = await list_obj.items.get(id="1")
            item.fields["Status"] = "Published"
            seeded = list_obj.items.with_objects(item)
            await seeded.update()
            ```
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
        Delete all list items in this queryset using `$batch`.

        Args:
            force:
                Safety flag. Must be `True` to execute deletes.

        Returns:
            int:
                Number of deleted items.

        Raises:
            RuntimeError:
                If `force` is not `True`.
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.
            RuntimeError:
                If any batch item fails (`utils.raise_batch_errors`).
        """
        if not force:
            raise RuntimeError("Set 'force=True' to proceed.")

        deleted = 0
        async for chunked_items in utils.achunks(self.select("id").all(), 20):
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
        """
        Resolve and normalize item collection path for requests.

        Internal helper that resolves `HOSTNAME` placeholders and, when needed,
        resolves list name paths to list-id paths before item operations.
        """
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
    items: QuerySetField[ListItemsQuerySet] = QuerySetField(ListItemsQuerySet)
    operations = ListField()
    subscriptions = ListField()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        """
        Return a concise debug representation of this SharePoint list.
        """
        return f"<List: {self.display_name or self.name}>"

    @property
    def path(self):
        """
        Resolve request path for this list.

        Returns:
            str:
                List path from object id or bound constructor path.
        """
        if self.id is None and (p := self._args[1]) is not None:
            return p
        return super().path

    async def get(self) -> "List":
        """
        Fetch and hydrate this list from Graph.

        Returns:
            List:
                Refreshed list model.

        Notes:
            If path contains `HOSTNAME`, it is resolved through
            `client.sites._get_hostname()` before request.
        """
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
        """
        Create a lazy list handle by list name.

        Args:
            name:
                SharePoint list display/name segment.

        Returns:
            List:
                List model bound to `{path}/{urlencoded_name}`.

        Raises:
            ValueError:
                If `name` is empty.
        """
        n = (name or "").strip()
        if not n:
            raise ValueError(f"{type(self).__name__} by_name requires a name.")
        n_encoded = quote(n, safe="")
        path = f"{self.path}/{n_encoded}"
        return List(client=self._client, path=path)


class FieldValueSet(PropertyModel):
    """
    Mutable list-item field payload with dirty-field tracking.

    Used by `ListItem.fields` to support partial PATCH updates of changed keys.
    """

    PATH = "/fields"

    def __getitem__(self, key: str) -> Any:
        """
        Read a field value by key.
        """
        return self._graph_data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Set a field value and mark it dirty if changed.
        """
        if self._graph_data.get(key) == value:
            return
        self._graph_data[key] = value
        self._dirty.add(key)

    def serialize(self) -> dict[str, Any]:
        """
        Build a Graph PATCH payload from tracked field changes.

        Returns:
            dict[str, Any]:
                Mapping of dirty SharePoint column names to their current
                values from `_graph_data`. Returns an empty dict when no
                fields have been modified.

        Notes:
            Schemaless counterpart of `Model.serialize()`: since
            `FieldValueSet` has no declared `Field` descriptors, the payload
            is read directly from `_graph_data` using `_dirty` as the key
            set. Safe to pass as `body=` to `utils.build_batch_requests` /
            `utils.send_batch_requests`.
        """
        return {k: self._graph_data[k] for k in self._dirty if k in self._graph_data}

    async def update(self, data: dict[str, Any] | None = None) -> bool:
        """
        Persist dirty field changes to Graph.

        Args:
            data:
                Optional dictionary of field updates to apply before persisting.
                Only existing keys are considered.

        Returns:
            bool:
                `True` if an update request was sent, otherwise `False`.

        Raises:
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.

        Example:
            ```python
            item = await list_obj.items.get(id="1")
            item.fields["Status"] = "Done"
            changed = await item.fields.update()
            ```
        """
        if data is not None:
            graph_data = self._graph_data
            for k, v in data.items():
                try:
                    self._graph_data[k]
                except KeyError:
                    continue
                graph_data[k] = v
                self._dirty.add(k)

        if not (payload := self.serialize()):
            return False
        await self._client.patch(self.path, body=payload)
        self._dirty.clear()
        return True
