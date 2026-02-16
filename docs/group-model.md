# Group Model

## Overview

- Model: `Group`
- Root queryset: `client.groups` (`GroupQuerySet`)
- Graph path: `/groups`
- Search field: `display_name`

## Common Properties

- Identity: `id`, `display_name`, `description`
- Mail/security: `mail`, `mail_enabled`, `mail_nickname`, `security_enabled`
- Classification/visibility: `group_types`, `visibility`, `classification`
- Navigation: `members`

Computed property:

- `group.group_type`: resolves to one of `microsoft365`, `security_mail_enabled`, `security`, `distribution`, or `unknown`

For full declared fields, see `src/pymsgraph/models/group/__init__.py`.

## GroupQuerySet

### Inherited QuerySet Operations

- `filter`, `exclude`, `search`
- `select`, `order_by`, `top`
- `get`, `first`, `count`, `values`

### Group-Specific QuerySet Methods

| API | Description |
|---|---|
| `await groups.create_security_group(...)` | Creates security-enabled group helper |
| `await groups.create_m365_group(...)` | Creates Unified (Microsoft 365) group helper |

## Members Relationship

`group.members` returns `MembersQuerySet` with member management helpers:

| API | Description |
|---|---|
| `await group.members.add(...)` | Add one or more directory objects as members (batched) |
| `await group.members.remove(...)` | Remove one or more members (batched) |
| `await group.members.copy_to(...)` | Copy current members to target group(s) |
| `group.members.users` | User-only view as `UsersQuerySet` |

## Example

```python
group = await client.groups.create_m365_group(
    display_name="Project Mercury",
    mail_nickname="project-mercury",
    visibility="Private",
)

await group.members.add("user-object-id")
```
