# Subscribed SKU Model

## Overview

- Model: `SubscribedSku`
- Root queryset: `client.subscribed_skus` (`SubscribedSkuQuerySet`)
- Graph path: `/subscribedSkus`
- Model is read-only

## Common Properties

- `sku_id`, `sku_part_number`, `account_name`, `consumed_units`, `capability_status`
- `prepaid_units` (`LicenseUnitsDetail`)
- `service_plans` (`ServicePlanInfo[]`)

Computed helpers:

| API | Description |
|---|---|
| `sku.product_name` | Friendly product name from static CSV mapping |
| `sku.available_units` | Computed available seats (`enabled + warning - consumed`) |
| `sku.has_available_units()` | True if available seats > 0 |

Class helpers:

| API | Description |
|---|---|
| `SubscribedSku.get_product_name(sku_id=... or sku_part_number=...)` | Resolve friendly product name |
| `SubscribedSku.get_sku_id(product_name)` | Resolve GUID sku id from product name |

## SubscribedSkuQuerySet

`SubscribedSkuQuerySet` inherits generic read/query operations and provides internal cache loading used by license-assignment helpers in user flows.

Common usage:

```python
skus = [s async for s in client.subscribed_skus]
for sku in skus:
    print(sku.sku_id, sku.product_name, sku.available_units)
```
