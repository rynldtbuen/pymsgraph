from typing import TYPE_CHECKING, Any
from pymsgraph.models.query import QuerySet
from pymsgraph.utils import chunks

if TYPE_CHECKING:
    from pymsgraph.models.user import User


class MembersQuerySet(QuerySet["User"]):
    PATH = "/members"
