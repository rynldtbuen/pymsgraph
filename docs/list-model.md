# List Model

## Overview

- Primary models:
  - `List`
  - `ListItem`
  - `FieldValueSet`
- Querysets:
  - `ListQuerySet`
  - `ListItemsQuerySet`

List resources are typically accessed from a site:

- `site.lists` -> `ListQuerySet`
- `list.items` -> `ListItemsQuerySet`

## Get a list by name

```python
site = await client.sites.get(path="/sites/Engineering")
list_obj = await site.lists.by_name("Tasks").get()

print(list_obj.id, list_obj.display_name)
```

## Create a list item

```python
site = await client.sites.get(path="/sites/Engineering")
list_obj = await site.lists.by_name("Tasks").get()

item = await list_obj.items.create(
    fields={
        "Title": "Quarterly review",
        "Status": "Draft",
    }
)

print(item.id)
```

## Create many list items

```python
site = await client.sites.get(path="/sites/Engineering")
list_obj = await site.lists.by_name("Tasks").get()

created = await list_obj.items.create_many(
    {"Title": "Task A", "Status": "New"},
    {"Title": "Task B", "Status": "In Progress"},
)

items = [i async for i in created]
print(len(items))
```

## Update list items (explicit fields)

```python
site = await client.sites.get(path="/sites/Engineering")
list_obj = await site.lists.by_name("Tasks").get()

updated = await list_obj.items.filter(id="1").update(Status="Completed")
print(updated)
```

## Update item fields with `FieldValueSet` (dirty tracking)

```python
site = await client.sites.get(path="/sites/Engineering")
list_obj = await site.lists.by_name("Tasks").get()

item = await list_obj.items.get(id="1")
item.fields["Title"] = "Renamed task"
item.fields["Status"] = "In Review"

changed = await item.fields.update()
print(changed)
```

## Delete list items (safety flag required)

```python
site = await client.sites.get(path="/sites/Engineering")
list_obj = await site.lists.by_name("Tasks").get()

deleted = await list_obj.items.filter(Status="Archived").delete(force=True)
print(deleted)
```

## Notes

- `ListItemsQuerySet.create_many`, `update`, and `delete` use Graph `$batch` operations.
- `ListItemsQuerySet.update()` without explicit fields uses dirty fields from cached/seeded `ListItem.fields`.
- `FieldValueSet` only sends changed keys when `update()` is called.
- `ListQuerySet.by_name(...)` returns a lazy list reference; call `.get()` to fetch it.

## API Reference

::: pymsgraph.models.site.list.List
    options:
      filters: public


::: pymsgraph.models.site.list.ListQuerySet
    options:
      filters: public


::: pymsgraph.models.site.list.ListItem
    options:
      filters: public


::: pymsgraph.models.site.list.ListItemsQuerySet
    options:
      filters: public


::: pymsgraph.models.site.list.FieldValueSet
    options:
      filters: public
