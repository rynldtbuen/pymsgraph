from __future__ import annotations

from pymsgraph.models.base import PropertyModel
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    DateTimeField,
    ListField,
    ModelField,
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
    received_date_time = DateTimeField(select_default=True, order_by=True)
    sender = ModelField(Recipient)
    sent_date_time = DateTimeField()
    subject = CharField(select_default=True, order_by=True)
    to_recipients = ListField(item_type=Recipient)
    web_link = CharField()

    def __repr__(self) -> str:
        return f"<Message: {self.subject or self.id}>"


class MessageQuerySet(QuerySet[Message]):
    """
    QuerySet for Microsoft Graph user messages (`/users/{id}/messages`).
    """

    model_class = Message
