# QuerySet

`QuerySet` is the core query builder in `pymsgraph`.
It is lazy, chainable, and designed around a Django-style API.

## Pagination

Pagination is handled by `iterator()`, which returns a paginator object.
The paginator supports:

- page-wise reads (`first_page()`, `next_page()`)
- metadata checks (`count()`, `has_next()`)

By default, querysets fetch one page unless `.all()` mode is enabled on the queryset iterator path.
Use explicit page size when you need predictable request sizing.

### Example

```python
# Build a base queryset with a stable projection/order for paging
qs = (
    client.users
    .filter(account_enabled=True)
    .select("display_name", "mail", "department")
    .order_by("display_name")
)

# Create paginator with an explicit page size
paginator = qs.iterator(page_size=25)

# Read first page
page1 = await paginator.first_page()
print(f"page1={len(page1)}")

# Optional metadata checks
total = await paginator.count()
has_next = await paginator.has_next()
print(f"total={total}, has_next={has_next}")

# Read next page when available
if has_next:
    page2 = await paginator.next_page()
    print(f"page2={len(page2)}")

# Iterate all remaining/current pages from paginator state
async for user in paginator.all():
    print(user.display_name, user.mail)
```

## API Reference

::: pymsgraph.models.query.QuerySet      
    options:
        filters: public
