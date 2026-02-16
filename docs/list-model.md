# List Model

## Overview

List resources are accessed from `Site`:

- `site.lists` -> `ListQuerySet`
- `list.items` -> `ListItemsQuerySet`

Primary models:

- `List`
- `ListItem`
- `FieldValueSet`

## List

| API | Description |
|---|---|
| `list.path` | Uses bound path for name/path-based references |
| `await list.get()` | Fetches list data, resolving hostname/list id path details |
| `site.lists.by_name("List Name")` | Build list reference by display name |

## ListQuerySet

Inherits generic queryset operations (`select`, `filter`, `top`, `get`, `values`, iteration) and adds:

| API | Description |
|---|---|
| `lists.by_name(name)` | Path-safe list reference by name |

## ListItem

`ListItem` exposes list item fields and a `fields` helper object:

| API | Description |
|---|---|
| `list_item.fields` | Returns `FieldValueSet` for dynamic SharePoint fields |

## ListItemsQuerySet

| API | Description |
|---|---|
| `await items.create(fields={...})` | Create one item |
| `await items.create_many(...)` | Batch create items |
| `await items.update(**fields)` | Batch update items (explicit fields) |
| `await items.update()` | Batch update dirty fields from cached objects |
| `await items.delete(force=True)` | Batch delete items |

## FieldValueSet

| API | Description |
|---|---|
| `field_set["InternalName"]` | Get field value |
| `field_set["InternalName"] = value` | Mark field dirty |
| `await field_set.update()` | Persist dirty fields |
| `await field_set.update({...})` | Merge/update provided values |

## Example

```python
lst = await client.sites.by_path("/sites/Engineering").lists.by_name("Tasks").get()

item = await lst.items.create(fields={"Title": "Initial task"})
item.fields["Title"] = "Renamed task"
await item.fields.update()
```
