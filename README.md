# pymsgraph

Python client for Microsoft Graph with model/query abstractions for resources such as users, groups, sites, drives, and list items.

## Requirements

- Python `3.12+`
- Microsoft Entra app registration with Graph permissions

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Authentication

`pymsgraph` accepts a token provider object with a `get_access_token(...)` method.
The repository includes MSAL-based providers:

- `ConfidentialClientAuth` for app-only flows
- `PublicClientAuth` for delegated flows

## Quick Start

```python
import asyncio
import logging
import os

from pymsgraph.auth import ConfidentialClientAuth
from pymsgraph.client import Client


async def main() -> None:
    logging.basicConfig(level=logging.INFO)  # use DEBUG for request/query tracing

    provider = ConfidentialClientAuth(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
    )

    async with Client(provider) as graph:
        # Fetch one user by id or UPN
        user = await graph.users.get(id="alice@contoso.com")
        print(user.id, user.display_name, user.mail)

        # Query users
        rows = await (
            graph.users
            .filter(account_enabled=True)
            .select("display_name", "mail")
            .order_by("display_name")
            .top(10)
            .values("display_name", "mail")
        )
        for row in rows:
            print(row)


if __name__ == "__main__":
    asyncio.run(main())
```

## User Guide: Create Users and Use `UserQuerySet`

### Create a single user

```python
user = await graph.users.create(
    display_name="Adele Vance",
    user_principal_name="adele.vance@contoso.com",
    mail_nickname="adele.vance",
    password="Pass@word123!",
    department="Engineering",
    job_title="Platform Engineer",
)

print(user.id, user.user_principal_name, user.display_name)
```

Required arguments for `create(...)`:
- `display_name`
- `user_principal_name`
- `mail_nickname`
- `password` (or use `auto_generate_password=True`)

### Create a user with an auto-generated password

```python
user = await graph.users.create(
    display_name="Megan Bowen",
    user_principal_name="megan.bowen@contoso.com",
    mail_nickname="megan.bowen",
    auto_generate_password=True,
)

# Returns the generated password once, then clears it from memory.
print(user.get_generated_password())
```

### Query users with `UserQuerySet`

```python
rows = await (
    graph.users
    .filter(account_enabled=True)
    .search(display_name="Adele")
    .select("display_name", "mail", "department")
    .order_by("display_name")
    .top(25)
    .values("display_name", "mail", "department")
)

for row in rows:
    print(row)
```

### Get a user by id or UPN

```python
user_by_id = await graph.users.get(id="0d5d1e6f-0000-0000-0000-000000000000")
user_by_upn = await graph.users.get(id="adele.vance@contoso.com")
```

### Bulk create users with `create_many`

```python
created = await graph.users.create_many(
    {
        "display_name": "User One",
        "user_principal_name": "user.one@contoso.com",
        "mail_nickname": "user.one",
        "password": "Pass@word123!",
    },
    {
        "display_name": "User Two",
        "user_principal_name": "user.two@contoso.com",
        "mail_nickname": "user.two",
        "password": "Pass@word123!",
    },
)

items = [u async for u in created]
print([u.id for u in items])
```

### Bulk operations from a queryset

```python
target_qs = graph.users.filter(department="Engineering")

# Batch assign manager to all users returned by the queryset.
await target_qs.assign_manager("manager-object-id")

# Batch reset passwords and export generated passwords to CSV.
await target_qs.reset_password(
    "reset-passwords.csv",
    auto_generate_password=True,
)
```

### User-specific helper querysets

```python
disabled_with_licenses = graph.users.disabled_with_assigned_licenses()
enabled_without_licenses = graph.users.enabled_with_no_assigned_licenses()
```

## Supported Models / Graph Resources

### Root QuerySets (available directly on `Client`)

| Client Property | Model / Resource | Graph Path | Coverage |
|---|---|---|---|
| `client.users` | `User` | `/users` | Query/filter/select/order/search, create/update/delete, manager assignment, password reset, member-of/app-role helpers |
| `client.groups` | `Group` | `/groups` | Query + create helpers (`create_security_group`, `create_m365_group`), member add/remove/copy helpers |
| `client.sites` | `Site` | `/sites` | Get by id/path, site path resolution (`by_path`), site drive and list navigation |
| `client.subscribed_skus` | `SubscribedSku` | `/subscribedSkus` | Read-only listing and SKU/product-name mapping helpers |

### Related / Nested Resources

| Model / Resource | Typical Entry Point | Graph Path Pattern | Coverage |
|---|---|---|---|
| `Drive` | `user.drive`, `site.drive` | `/users/{id}/drive`, `/sites/{...}/drive` | Drive resolution and root navigation |
| `DriveItem` | `drive.root`, `drive.root.by_path(...)`, `...by_id(...)` | `/drives/{id}/root...`, `/users/{id}/drive/items...` | Children listing, get by id/path, upload/download, copy/move |
| `List` | `site.lists`, `site.lists.by_name(...)` | `/sites/{id}/lists...` | List retrieval and list-id/name resolution |
| `ListItem` | `list.items` | `/sites/{id}/lists/{id}/items...` | Create/create_many, update (explicit or dirty fields), delete (batched) |
| `AppRoleAssignment` | `user.app_role_assignments` | `/users/{id}/appRoleAssignments` | Read/query assignment data |

### Additional Implemented Models

- `DirectoryObject`, `AdministrativeUnit`, `DirectoryRole`
- `ServicePrincipal` and `ServicePrincipalQuerySet` (model/queryset available in codebase; not currently exposed as a root property on `Client`)
- Shared/common value models under `pymsgraph.models.common` and `pymsgraph.models.user.common`

Notes:
- This library intentionally implements a practical subset of Microsoft Graph resources and fields.
- Coverage expands over time; unsupported fields/endpoints can be added incrementally.

## Common Operations

### Create a Security Group

```python
group = await graph.groups.create_security_group(
    display_name="Operations Team",
    mail_nickname="operations-team",
)
print(group.id, group.display_name)
```

### Create a Microsoft 365 Group

```python
group = await graph.groups.create_m365_group(
    display_name="Project Mercury",
    mail_nickname="project-mercury",
    visibility="Private",  # or Public
)
print(group.id, group.display_name)
```

### Resolve a Site by Path and Browse Drive Items

```python
site = await graph.sites.get(path="/sites/Engineering")
folder = site.drive.root.by_path("/Shared Documents")

items = [item async for item in folder.items.top(5)]
for item in items:
    print(item.id, item.name, item.size)
```

