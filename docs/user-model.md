# User Model

## Overview

- Model: `User`
- Root queryset: `client.users` (`UserQuerySet`)
- Graph path: `/users`


## Create a user

```python
user = await client.users.create(
    display_name="Adele Vance",
    user_principal_name="adele.vance@contoso.com",
    mail_nickname="adele.vance",
    password="Pass@word123!",
    department="Engineering",
    job_title="Platform Engineer",
)

print(user.id, user.display_name, user.user_principal_name)
```

## Create a user with auto-generated password

```python
user = await client.users.create(
    display_name="Megan Bowen",
    user_principal_name="megan.bowen@contoso.com",
    mail_nickname="megan.bowen",
    auto_generate_password=True,
)

# Returns once, then clears internal cache.
print(user.get_generated_password())
```

## Create a user and assign manager / licenses

```python
user = await client.users.create(
    display_name="Robin Counts",
    user_principal_name="robin.counts@contoso.com",
    mail_nickname="robin.counts",
    auto_generate_password=True,
    manager="manager@contoso.com",
    assign_licenses=[
        "6fd2c87f-b296-42f0-b197-1e91e994b900",  # sku id
        "Microsoft Business Premium" # product name
    ],
)
```

## Bulk create users (Inline Records)

```python
created_qs = await client.users.create_many(
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

created_users = [u async for u in created_qs]
print([u.id for u in created_users])
```

## Bulk create users from CSV

```python
created_qs = await client.users.create_many(
    path="new-users.csv",
    auto_generate_password=True,
    export_path="created-users.csv",  # exports generated passwords
)

created_users = [u async for u in created_qs]
print(len(created_users))
```

## Update user fields

```python
# Update a single user
user = await client.users.get(id="adele.vance@contoso.com")
await user.update(
    job_title="Senior Platform Engineer",
    department="Architecture",
    mobile_phone="+1 555 0100",
)

# Bulk update users matched by a queryset
updated_count = await client.users.filter(department="Engineering").update(
    city="Seattle",
    usage_location="US",
)
print(updated_count)
```

## Notes

- `create_many(...)` supports both inline dict records and CSV input (`path=...`).
- If `password` is omitted, set `auto_generate_password=True`.
- `create(...)` can assign manager and licenses at creation time.

## API Reference

::: pymsgraph.models.user.User
    options:
      filters: public


::: pymsgraph.models.user.UserQuerySet
    options:
      filters: public


::: pymsgraph.models.user.query.AssignedLicensesQuerySetProxy
    options:
      filters: public
