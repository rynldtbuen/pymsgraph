from __future__ import annotations

import re
import secrets
import string
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

# if TYPE_CHECKING:
#     from pymsgraph.models.base import TModel, Model
#     from pymsgraph.query import QuerySet


def generate_password(length: int = 12) -> str:
    """
    Generate a strong random password.

    Guarantees:
    - length >= 12 (enforced)
    - at least 1 lowercase, 1 uppercase, 1 digit, 1 symbol

    Uses `secrets` for cryptographic randomness.
    """
    if length < 12:
        raise ValueError("length must be at least 12")

    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    # Avoid quotes/backslash which can be annoying in some contexts
    symbols = "!@#$%^&*()-_=+?"

    # Ensure required categories
    required = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]

    all_chars = lowercase + uppercase + digits + symbols

    # Fill the rest
    remaining = [secrets.choice(all_chars) for _ in range(length - len(required))]

    # Shuffle so required chars aren't predictable positions
    chars = required + remaining
    secrets.SystemRandom().shuffle(chars)

    return "".join(chars)


_CAMEL_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_2 = re.compile(r"([a-z0-9])([A-Z])")


def to_snake_case(s: str) -> str:
    """
    Convert camelCase / PascalCase to snake_case.

    Examples:
        "displayName" -> "display_name"
        "UserPrincipalName" -> "user_principal_name"
        "SKUId" -> "sku_id"
        "servicePlanId2" -> "service_plan_id2"
    """
    s = s.strip()
    if not s:
        return s

    s = s.replace("-", "_").replace(" ", "_")
    s = _CAMEL_1.sub(r"\1_\2", s)
    s = _CAMEL_2.sub(r"\1_\2", s)
    return s.lower()


def to_camel_case(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


# def get_model_class(model_name: str) -> type[Model]:
#     module_name = camel_to_snake(model_name)
#     mod = importlib.import_module(f"pymsgraph.models.{module_name}")
#     return getattr(mod, model_name)


# def get_queryset_class(queryset_path: str):
#     module_name, _, cls_name = queryset_path.rpartition(".")
#     if not module_name or not cls_name:
#         raise ImportError(f"Invalid qs_path, '{queryset_path}'")

#     mod = importlib.import_module(f"pymsgraph.models.{module_name}")
#     return getattr(mod, cls_name)


# T = TypeVar("T")


# def chunks(iterable: Iterable[T], size: int = 2) -> Iterator[list[T]]:
#     if size <= 2:
#         raise ValueError("Size must be > 2")

#     batch: list[T] = []
#     for item in iterable:
#         batch.append(item)
#         if len(batch) == size:
#             yield batch
#             batch = []
#     if batch:
#         yield batch


# def coerce_objects(
#     *args: str | TModel | Iterable[str] | Iterable[TModel] | QuerySet[TModel],
#     queryset: QuerySet[TModel],  # pyright: ignore[reportRedeclaration]
#     key: str = "id",
# ) -> Iterator[TModel]:
#     def _is_iterable_but_not_str(x: Any) -> bool:
#         return isinstance(x, Iterable) and not isinstance(
#             x, (str, bytes, bytearray, dict)
#         )

#     def _iter_flatten(
#         *args: str | TModel | Iterable[str] | Iterable[TModel] | QuerySet[TModel],
#     ) -> Iterator[TModel]:
#         for arg in args:
#             if isinstance(arg, str):
#                 yield queryset.make(**{key: arg})
#             elif isinstance(arg, Model):
#                 yield arg
#             elif _is_iterable_but_not_str(arg):
#                 yield from _iter_flatten(*arg)
#             elif isinstance(arg, QuerySet):
#                 yield from arg
#             else:
#                 continue

#     from pymsgraph.models.base import Model
#     from pymsgraph.query import QuerySet

#     # if isinstance(model_class, str):
#     #     model_class: type[TModel] = cast(type[TModel], get_model_class(model_class))

#     seen: set[str] = set()

#     for obj in _iter_flatten(*args):
#         try:
#             val = getattr(obj, key)
#         except AttributeError:
#             continue
#         if val not in seen:
#             yield obj
#         seen.add(val)


# def compile_collection_lookup(
#     *,
#     field_name: str,
#     element_field: bool | str | None = None,
#     var: str = "x",
# ) -> Callable[[str, Any], str]:
#     """
#     Build an any() lookup for a collection.

#     - scalar collection: otherMails/any(x:endswith(x,'@edu'))
#     - object collection: assignedLicenses/any(u:u/skuId eq <value>)
#     """

#     def _compile(lookup: str, value: Any) -> str:
#         graph_field = snake_to_camel(field_name)
#         if lookup == "isnull":
#             if not isinstance(value, bool):
#                 raise ValueError(f"Value is not an instance of bool, {value!r}")
#             return (
#                 f"{graph_field}/$count eq 0" if value else f"{graph_field}/$count ne 0"
#             )

#         if element_field:
#             if element_field is True:
#                 if "__" in lookup:
#                     element, op = lookup.split("__", 1)
#                 else:
#                     element, op = lookup, "exact"
#                 if not element:
#                     raise ValueError(f"Unsupported lookup for collection: {lookup!r}")
#             else:
#                 element = str(element_field)
#                 if lookup.startswith(f"{element}__"):
#                     op = lookup.split("__", 1)[1] or "exact"
#                 elif lookup == element:
#                     op = "exact"
#                 else:
#                     raise ValueError(f"Unsupported lookup for {element}: {lookup!r}")

#             ef_graph = snake_to_camel(element)
#             clause = compile_lookup(f"{var}/{ef_graph}", op, value)
#             return f"{graph_field}/any({var}:{clause})"

#         clause = compile_lookup(var, lookup or "exact", value)
#         return f"{graph_field}/any({var}:{clause})"

#     return _compile


def raise_batch_errors(batch_payload: dict[str, Any], *, action: str) -> None:
    # Graph returns 200 for the batch envelope even if individual requests failed. :contentReference[oaicite:2]{index=2}
    for r in batch_payload.get("responses", []) or []:
        status = int(r.get("status", 0) or 0)
        if status >= 400:
            body = r.get("body")
            raise RuntimeError(f"Batch {action} failed (status={status}): {body}")
