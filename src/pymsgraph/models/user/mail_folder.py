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

WELL_KNOWN_MAIL_FOLDERS: dict[str, str] = {
    "archive": "archive",
    "clutter": "clutter",
    "conflicts": "conflicts",
    "conversation_history": "conversationhistory",
    "deleted_items": "deleteditems",
    "drafts": "drafts",
    "inbox": "inbox",
    "junk_email": "junkemail",
    "local_failures": "localfailures",
    "msg_folder_root": "msgfolderroot",
    "outbox": "outbox",
    "recoverable_items_deletions": "recoverableitemsdeletions",
    "scheduled": "scheduled",
    "search_folders": "searchfolders",
    "sent_items": "sentitems",
    "server_failures": "serverfailures",
    "sync_issues": "syncissues",
}

_WELL_KNOWN_MAIL_FOLDER_VALUES = frozenset(WELL_KNOWN_MAIL_FOLDERS.values())


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

    def by_id(self, id: str) -> "MailFolder":
        """
        Create a lazy child folder handle from a child folder id.

        This is a convenience shortcut for `mail_folder.child_folders.by_id(id)`.

        Args:
            id:
                Child mail folder id.

        Returns:
            MailFolder:
                Lazy child folder model bound to `{mail_folder.path}/childFolders/{id}`.
        """
        return self.child_folders.by_id(id)

    def __repr__(self) -> str:
        return f"<MailFolder: {self.display_name or self.id}>"


class MailFolderQuerySet(QuerySet[MailFolder]):
    """
    QuerySet for Microsoft Graph mail folders (`.../mailFolders`).
    """

    model_class = MailFolder

    def by_id(self, id: str) -> MailFolder:
        """
        Create a lazy mail folder handle from a folder id.

        This does not send a Graph request. It returns a `MailFolder` bound to
        the current queryset path, so it works for root mail folders and child
        folder querysets.

        Args:
            id:
                Mail folder id.

        Returns:
            MailFolder:
                Lazy mail folder model bound to `{queryset.path}/{id}`.

        Raises:
            ValueError:
                If `id` is empty, path-like, a display-name path, or a
                well-known folder name.

        Example:
            ```python
            folder = (
                client.users
                .by_id("alice@contoso.com")
                .mail_folders
                .by_id("AQMkAD...")
            )
            messages = [m async for m in folder.messages]
            ```
        """
        value = _validate_mail_folder_id(id, type(self).__name__)

        return MailFolder(client=self._client, path=self.path, id=value)

    def _well_known(self, name: str) -> MailFolder:
        return MailFolder(client=self._client, path=self.path, id=name)

    @property
    def archive(self) -> MailFolder:
        return self._well_known("archive")

    @property
    def clutter(self) -> MailFolder:
        return self._well_known("clutter")

    @property
    def conflicts(self) -> MailFolder:
        return self._well_known("conflicts")

    @property
    def conversation_history(self) -> MailFolder:
        return self._well_known("conversationhistory")

    @property
    def deleted_items(self) -> MailFolder:
        return self._well_known("deleteditems")

    @property
    def drafts(self) -> MailFolder:
        return self._well_known("drafts")

    @property
    def inbox(self) -> MailFolder:
        return self._well_known("inbox")

    @property
    def junk_email(self) -> MailFolder:
        return self._well_known("junkemail")

    @property
    def local_failures(self) -> MailFolder:
        return self._well_known("localfailures")

    @property
    def msg_folder_root(self) -> MailFolder:
        return self._well_known("msgfolderroot")

    @property
    def outbox(self) -> MailFolder:
        return self._well_known("outbox")

    @property
    def recoverable_items_deletions(self) -> MailFolder:
        return self._well_known("recoverableitemsdeletions")

    @property
    def scheduled(self) -> MailFolder:
        return self._well_known("scheduled")

    @property
    def search_folders(self) -> MailFolder:
        return self._well_known("searchfolders")

    @property
    def sent_items(self) -> MailFolder:
        return self._well_known("sentitems")

    @property
    def server_failures(self) -> MailFolder:
        return self._well_known("serverfailures")

    @property
    def sync_issues(self) -> MailFolder:
        return self._well_known("syncissues")


def _validate_mail_folder_id(value: str, owner: str) -> str:
    folder_id = (value or "").strip()
    if not folder_id:
        raise ValueError(f"{owner}.by_id requires a mail folder id.")
    if "/" in folder_id or "\\" in folder_id:
        raise ValueError(
            f"{owner}.by_id requires a folder id, not a folder path. "
            "Use child_folders.by_id(...) to navigate nested folders."
        )
    if any(c.isspace() for c in folder_id):
        raise ValueError(
            f"{owner}.by_id requires a folder id, not a display-name path."
        )
    if (
        folder_id in WELL_KNOWN_MAIL_FOLDERS
        or folder_id in _WELL_KNOWN_MAIL_FOLDER_VALUES
    ):
        raise ValueError(
            f"{owner}.by_id only accepts folder ids. "
            f"Use the well-known folder property instead, for example `{owner}.inbox`."
        )
    return folder_id
