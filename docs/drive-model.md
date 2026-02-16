# Drive Model

## Overview

Drive resources are accessed via parent resources (for example `user.drive` or `site.drive`), not from a root `client.drives` queryset.

Primary models:

- `Drive`
- `DriveItem`
- `DriveItemsQueryset` (children/item traversal)

## Drive

| API | Description |
|---|---|
| `drive.path` | Uses bound path for path-based drive references |
| `drive.root` | Returns root `DriveItem` reference |
| `await drive.get()` | Fetches drive data |
| `await Drive.from_path(client, path)` | Resolve and fetch drive by arbitrary Graph path |

## DriveItem

### Common Properties

- `id`, `name`, `size`, `file`, `folder`, `web_url`, `sharepoint_ids` (and other declared fields)

### Methods and Navigation

| API | Description |
|---|---|
| `drive_item.items` | Children queryset (`/children` semantics) |
| `drive_item.by_path("/folder/file")` | Build path-based child reference |
| `drive_item.by_id("item-id")` | Build id-based child reference |
| `await drive_item.get()` | Fetch item data |
| `await drive_item.upload(...)` | Upload file content (bytes/string/file path) |
| `await drive_item.download(dest_path=...)` | Download file content |
| `await drive_item.copy(...)` | Copy item (optionally with destination parent) |
| `await drive_item.move(...)` | Move/rename item |

## DriveItemsQueryset

`DriveItemsQueryset` extends iteration/path resolution for children listings and path normalization across:

- `/drives/{id}/root...`
- `/users/{id}/drive/root...`
- `/sites/{hostname}:/...:/drive/root...`

Use inherited queryset operators such as `top`, `select`, `filter`, and async iteration.

## Example

```python
folder = user.drive.root.by_path("/Shared Documents")
children = [item async for item in folder.items.top(25)]

uploaded = await folder.by_id("folder-id").upload(
    name="hello.txt",
    content="hello world",
    content_type="text/plain",
)
```
