from __future__ import annotations

from pymsgraph.models.base import PropertyModel
from pymsgraph.models.fields import BooleanField, CharField, IntegerField
from pymsgraph.models.query import QuerySet


class MailFolder(PropertyModel):
    """
    Graph `mailFolder` resource.

    https://learn.microsoft.com/en-us/graph/api/resources/mailfolder
    """

    PATH = "/mailFolders"

    child_folder_count = IntegerField()
    display_name = CharField(select_default=True, order_by=True)
    is_hidden = BooleanField()
    parent_folder_id = CharField()
    total_item_count = IntegerField()
    unread_item_count = IntegerField()
    well_known_name = CharField()

    def __repr__(self) -> str:
        return f"<MailFolder: {self.display_name or self.id}>"


class MailFolderQuerySet(QuerySet[MailFolder]):
    """
    QuerySet for Microsoft Graph mail folders (`.../mailFolders`).
    """

    model_class = MailFolder
