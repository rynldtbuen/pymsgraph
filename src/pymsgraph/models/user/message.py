from __future__ import annotations

import base64
from pathlib import Path

from pymsgraph.models.base import PropertyModel
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    DateTimeField,
    IntegerField,
    ListField,
    ModelField,
    QuerySetField,
)
from pymsgraph.models.query import QuerySet


class EmailAddress(PropertyModel):
    """
    Graph `emailAddress` complex type.

    https://learn.microsoft.com/en-us/graph/api/resources/emailaddress
    """

    address = CharField()
    name = CharField()


class Recipient(PropertyModel):
    """
    Graph `recipient` complex type.

    https://learn.microsoft.com/en-us/graph/api/resources/recipient
    """

    email_address = ModelField(EmailAddress)


class ItemBody(PropertyModel):
    """
    Graph `itemBody` complex type.

    https://learn.microsoft.com/en-us/graph/api/resources/itembody
    """

    content = CharField()
    content_type = CharField()


class Attachment(PropertyModel):
    """
    Graph message attachment resource.

    Supports common attachment fields shared across Graph attachment types.

    https://learn.microsoft.com/en-us/graph/api/resources/attachment
    """

    PATH = "/attachments"

    content_id = CharField()
    content_location = CharField()
    content_type = CharField()
    is_inline = BooleanField()
    last_modified_date_time = DateTimeField()
    name = CharField(select_default=True, order_by=True)
    size = IntegerField()

    # FileAttachment-specific fields. These may be null for other attachment types.
    content_bytes = CharField(graph_attr_name="contentBytes")

    def __repr__(self) -> str:
        return f"<Attachment: {self.name or self.id}>"


class AttachmentQuerySet(QuerySet[Attachment]):
    """
    QuerySet for message attachments (`.../messages/{id}/attachments`).
    """

    model_class = Attachment

    async def download(self, dest_dir: str | Path | None = None) -> dict[str, bytes]:
        """
        Download all attachments in this queryset.

        For each attachment:
        - use `contentBytes` when available
        - otherwise fetch bytes from `GET {attachments-path}/{id}/$value`

        Args:
                dest_dir:
                        Optional destination directory. When provided, each downloaded
                        attachment is written to disk using attachment `name` (or `id`).

        Returns:
                dict[str, bytes]:
                        Mapping of `attachment.id` to downloaded bytes.
        """
        out_dir: Path | None = None
        if dest_dir is not None:
            out_dir = Path(dest_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

        downloaded: dict[str, bytes] = {}
        used_filenames: set[str] = set()

        async for attachment in self:
            if not attachment.id:
                continue

            data: bytes
            if attachment.content_bytes:
                data = base64.b64decode(attachment.content_bytes)
            else:
                data = await self._client.get_content(
                    f"{self.path}/{attachment.id}/$value"
                )

            downloaded[attachment.id] = data

            if out_dir is not None:
                base_name = attachment.name or attachment.id
                candidate = base_name
                index = 2
                while candidate in used_filenames:
                    candidate = f"{base_name}_{index}"
                    index += 1
                used_filenames.add(candidate)
                (out_dir / candidate).write_bytes(data)

        return downloaded


class Message(PropertyModel):
    """
    Graph `message` resource.

    Minimal message model for user mailbox operations. Additional actions and
    helpers (send/move/reply/attachments) can be added incrementally.

    https://learn.microsoft.com/en-us/graph/api/resources/message
    """

    PATH = "/messages"

    # Core properties
    bcc_recipients = ListField(item_type=Recipient)
    body = ModelField(ItemBody)
    body_preview = CharField()
    cc_recipients = ListField(item_type=Recipient)
    conversation_id = CharField()
    conversation_index = CharField()
    created_date_time = DateTimeField()
    from_ = ModelField(Recipient, graph_attr_name="from")
    has_attachments = BooleanField()
    importance = CharField()
    internet_message_id = CharField()
    is_draft = BooleanField()
    is_read = BooleanField(select_default=True)
    parent_folder_id = CharField()
    received_date_time = DateTimeField(select_default=True, order_by=True)
    sender = ModelField(Recipient)
    sent_date_time = DateTimeField()
    subject = CharField(select_default=True, order_by=True)
    to_recipients = ListField(item_type=Recipient)
    unique_body = ModelField(ItemBody)
    web_link = CharField()
    attachments = QuerySetField(AttachmentQuerySet)

    @property
    def path(self) -> str:
        """
        Resolve Graph path for this message.

        Returns:
                str:
                        Collection path when `id` is missing, otherwise item path
                        ending with `/{id}`.
        """
        base_path = str(self._args[1] or self.PATH or "").rstrip("/")
        if not base_path:
            raise AttributeError(
                f"{type(self).__name__} object has no attribute 'path'"
            )

        if not self.id:
            raise AttributeError(f"{type(self).__name__} object has no attribute, 'id'")

        if base_path.endswith(f"/{self.id}"):
            return base_path
        return f"{base_path}/{self.id}"

    def __repr__(self) -> str:
        return f"<Message: {self.subject or self.id}>"

    async def download(self, dest_path: str | Path | None = None) -> bytes:
        """
        Download this message as raw MIME content.

        This calls Microsoft Graph:
        `GET {message-path}/$value`.

        Args:
                dest_path:
                        Optional file path. When provided, the downloaded MIME bytes
                        are also written to disk.

        Returns:
                bytes:
                        Raw message bytes returned by Graph (`.eml` content).

        Raises:
                AttributeError:
                        If this message has no `id`.
                httpx.HTTPStatusError:
                        If Graph returns an HTTP error.

        Example:
                ```python
                mime_bytes = await message.download("message.eml")
                ```
        """
        data = await self._client.get_content(f"{self.path}/$value")
        if dest_path is not None:
            Path(dest_path).write_bytes(data)
        return data

    async def move(self, destination_id: str) -> "Message":
        """
        Move this message to another mail folder.

        This calls Microsoft Graph:
        `POST {message-path}/move` with body `{"destinationId": "<folder-id>"}`.

        Args:
                destination_id:
                        Destination mail folder id.

        Returns:
                Message:
                        The moved message returned by Graph.

        Raises:
                ValueError:
                        If `destination_id` is empty.
                httpx.HTTPStatusError:
                        If Graph returns an HTTP error.

        Example:
                ```python
                moved = await message.move("AQMkAD...folder-id")
                print(moved.parent_folder_id)
                ```
        """
        if not destination_id:
            raise ValueError("destination_id is required.")

        if not self.id:
            raise AttributeError(f"{type(self).__name__} object has no attribute, 'id'")

        base_path = str(self._args[1] or self.PATH or "").rstrip("/")
        message_path = self.path
        parent_path = (
            base_path[: -(len(self.id) + 1)]
            if base_path.endswith(f"/{self.id}")
            else base_path
        )

        data = await self._client.post(
            f"{message_path}/move", body={"destinationId": destination_id}
        )
        return type(self).from_graph(data, client=self._client, path=parent_path)


class MessageQuerySet(QuerySet[Message]):
    """
    QuerySet for Microsoft Graph user messages (`/users/{id}/messages`).
    """

    model_class = Message

    def by_id(self, id: str) -> Message:
        """
        Create a lazy message handle from a message id.

        This does not send a Graph request. It returns a `Message` bound to the
        current queryset path, so the same method works for user messages and
        mail-folder messages.

        Args:
            id:
                Message id.

        Returns:
            Message:
                Lazy message model bound to `{queryset.path}/{id}`.

        Raises:
            ValueError:
                If `id` is empty.

        Example:
            ```python
            message = user.messages.by_id("AQMkAD...")
            await message.move("archive-folder-id")
            ```
        """
        value = (id or "").strip()
        if not value:
            raise ValueError(f"{type(self).__name__}.by_id requires a message id.")

        return Message(client=self._client, path=self.path, id=value)
