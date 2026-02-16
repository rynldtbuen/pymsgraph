# Site Model

## Overview

- Model: `Site`
- Root queryset: `client.sites` (`SiteQuerySet`)
- Graph path: `/sites`

## Common Properties

- `id`, `display_name`, `name`
- `site_collection`, `sharepoint_ids`
- `is_personal_site`

Navigation properties:

- `site.drive` -> `Drive`
- `site.lists` -> `ListQuerySet`

## Site Instance Methods

| API | Description |
|---|---|
| `site.path` | Uses bound path when created with path-based access |
| `await site.get()` | Fetches/refreshes this site, resolving `HOSTNAME` placeholders |

## SiteQuerySet

### Inherited QuerySet Operations

- `filter`, `exclude`, `select`, `order_by`, `top`, `first`, `count`, `values`

### Site-Specific Methods

| API | Description |
|---|---|
| `sites.search(keyword="...")` | Search sites (keyword only; no `Q`/kwargs mix) |
| `await sites.get(id="...")` | Get by site id |
| `await sites.get(path="/sites/...")` | Get by SharePoint path, with hostname discovery/cache |
| `sites.by_path("/sites/...")` | Build path-based `Site` reference (lazy) |
| `await sites._get_hostname()` | Internal hostname resolution/cache helper |

## Example

```python
site = await client.sites.get(path="/sites/Engineering")
drive = site.drive
lists_qs = site.lists
```
