from __future__ import annotations

from pymsgraph.models.base import ReadOnlyModel
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    IntegerField,
    QuerySetField,
)
from pymsgraph.models.query import QuerySet
from .message import MessageQuerySet


class MailFolder(ReadOnlyModel):
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

    # Navigation properties
    messages = QuerySetField(MessageQuerySet, prefetch=True)

    @property
    def child_folders(self) -> "MailFolderQuerySet":
        """
        Return child folders for this mail folder.

        Returns:
            MailFolderQuerySet:
                Queryset bound to `{mail_folder.path}/childFolders`.
        """
        kwargs = {
            "path": f"{self.path}/childFolders",
            "model_class": MailFolder,
            "obj": self,
        }
        cached_data = self._data.get("child_folders")
        if cached_data is None:
            cached_data = self._graph_data.get("childFolders")
        if cached_data:
            kwargs["cached_data"] = cached_data
        if hasattr(self, "_prefetch_meta"):
            meta = self._prefetch_meta.get("child_folders", {})
            if meta.get("next_link"):
                kwargs["prefetch_next_link"] = meta["next_link"]
            if meta.get("count") is not None:
                kwargs["prefetch_count"] = int(meta["count"])
        return MailFolderQuerySet(self._client, **kwargs)

    def __repr__(self) -> str:
        return f"<MailFolder: {self.display_name or self.id}>"


class MailFolderQuerySet(QuerySet[MailFolder]):
    """
    QuerySet for Microsoft Graph mail folders (`.../mailFolders`).
    """

    model_class = MailFolder
