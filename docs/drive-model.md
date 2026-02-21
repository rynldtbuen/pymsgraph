# Drive Model

## Overview

Drive resources are accessed from parent resources (for example `user.drive` or
`site.drive`) rather than a root `client.drives` queryset.

- Primary models:
  - `Drive`
  - `DriveItem`
  - `DriveItemsQueryset`

## Get a drive from user/site

```python
user = await client.users.get(id="alice@contoso.com")
user_drive = await user.drive.get()

site = await client.sites.get(path="/sites/Engineering")
site_drive = await site.drive.get()

print(user_drive.id, site_drive.id)
```

## Get drive by arbitrary path

```python
drive = await Drive.from_path(
    client,
    "/sites/contoso.sharepoint.com:/sites/Engineering:/drive",
)
print(drive.id, drive.name)
```

## Browse drive items

```python
drive = await client.users.get(id="alice@contoso.com").drive.get()

root = drive.root
children = [item async for item in root.items.top(25)]
print(len(children))
```

## Resolve item by path or id

```python
drive = await client.users.get(id="alice@contoso.com").drive.get()

docs_folder = drive.root.by_path("/Shared Documents")
docs_folder = await docs_folder.get()

same_folder = drive.root.by_id(docs_folder.id)
same_folder = await same_folder.get()
```

## Upload and download file

```python
drive = await client.users.get(id="alice@contoso.com").drive.get()
folder = await drive.root.by_path("/Shared Documents").get()

uploaded = await folder.upload(
    name="hello.txt",
    content="hello world",
    content_type="text/plain",
)

content = await uploaded.download()
print(len(content))
```

## Copy and move item

```python
drive = await client.users.get(id="alice@contoso.com").drive.get()
folder = await drive.root.by_path("/Shared Documents").get()
item = await folder.by_path("/hello.txt").get()

copied = await item.copy(name="hello-copy.txt")
moved = await copied.move(name="hello-renamed.txt")
print(moved.name)
```

## Notes

- `DriveItem.items` returns `DriveItemsQueryset` and normalizes child traversal paths.
- `DriveItem.by_path(...)` is lazy; call `await .get()` to fetch the item.
- Site-based drive/item paths may contain `HOSTNAME` placeholders and are resolved automatically.
- Upload uses simple upload (`...:/content`) and is suitable for small files.

## API Reference

::: pymsgraph.models.drive.Drive
    options:
      filters: public

::: pymsgraph.models.drive.DriveItem
    options:
      filters: public


::: pymsgraph.models.drive.DriveItemsQueryset
    options:
      filters: public
```
