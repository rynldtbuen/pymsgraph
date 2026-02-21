# Group Model

## Overview

- Model: `Group`
- Root queryset: `client.groups` (`GroupQuerySet`)
- Graph path: `/groups`

## Create a security group

```python
group = await client.groups.create_security_group(
    display_name="Platform Security",
    mail_nickname="platform-security",
)

print(group.id, group.display_name, group.group_type)
```

## Create a mail-enabled security group

```python
group = await client.groups.create_security_group(
    display_name="Ops Notifications",
    mail_nickname="ops-notifications",
    mail_enabled=True,
)

print(group.mail_enabled, group.security_enabled, group.group_type)
```

## Create a Microsoft 365 group

```python
group = await client.groups.create_m365_group(
    display_name="Project Mercury",
    mail_nickname="project-mercury",
    visibility="Private",
)

print(group.id, group.display_name, group.group_type)
```

## Add and remove members

```python
group = await client.groups.get(id="group-object-id")

await group.members.add(
    "user-object-id-1",
    "user-object-id-2",
)

await group.members.remove("user-object-id-2")
```

## Copy members to another group

```python
source = await client.groups.get(id="source-group-id")
await source.members.copy_to("target-group-id")
```

## User-only member queryset

```python
group = await client.groups.get(id="group-object-id")

user_members_qs = group.members.users
user_members = [u async for u in user_members_qs]
print(len(user_members))
```

## Update group fields

```python
group = await client.groups.get(id="group-object-id")
await group.update(description="Platform security and access control group")

updated = await client.groups.filter(classification="Internal").update(
    visibility="Private",
)
print(updated)
```

## Notes

- `group.group_type` is computed from `group_types`, `mail_enabled`, and `security_enabled`.
- `group.members.add/remove/copy_to` use Graph batching under the hood (chunked requests).
- `group.members.users` provides a user-only view of the group membership relationship.
- Microsoft Graph member-management APIs (`add/remove members`, `add/remove owners`) are supported for **security groups** and **Microsoft 365 groups**.
- **Distribution lists** and **mail-enabled security groups** are Exchange-managed and are not supported by these Graph group membership update APIs.

## API Reference

::: pymsgraph.models.group.Group
    options:
      filters: public


::: pymsgraph.models.group.GroupQuerySet
    options:
      filters: public


::: pymsgraph.models.group.query.MembersQuerySet
    options:
      filters: public


::: pymsgraph.models.group.query.UsersQuerySet
    options:
      filters: public
