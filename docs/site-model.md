# Site Model

## Overview

- Model: `Site`
- Root queryset: `client.sites` (`SiteQuerySet`)
- Graph path: `/sites`

## Get a site by id

```python
site = await client.sites.get(id="contoso.sharepoint.com,123,456")
print(site.id, site.display_name)
```

## Get a site by SharePoint path

```python
site = await client.sites.get(path="/sites/Engineering")
print(site.id, site.display_name)
```

## Build a lazy site reference by path

```python
# by_path() returns a lazy Site handle (no request yet)
lazy_site = client.sites.by_path("/sites/Engineering")

# get() resolves HOSTNAME and fetches the site
site = await lazy_site.get()
print(site.id, site.display_name)
```

## Search sites by keyword

```python
sites_qs = client.sites.search(keyword="Engineering").top(10)
sites = [s async for s in sites_qs]
print(len(sites))
```

## Access site drive and lists

```python
site = await client.sites.get(path="/sites/Engineering")

drive = site.drive
lists_qs = site.lists

print(drive.path)
print(lists_qs.path)
```

## Get a list under a site

```python
site = await client.sites.get(path="/sites/Engineering")
list_obj = await site.lists.by_name("Documents").get()
print(list_obj.id, list_obj.display_name)
```

## Notes

- `client.sites.by_path(...)` builds a lazy `Site` reference and may include a `HOSTNAME` placeholder.
- `await site.get()` resolves `HOSTNAME` via `/sites/root` hostname discovery when needed.
- `site.drive` and `site.lists` automatically preserve path-based URL formatting rules.

## API Reference

::: pymsgraph.models.site.Site
    options:
      filters: public


::: pymsgraph.models.site.SiteQuerySet
    options:
      filters: public
