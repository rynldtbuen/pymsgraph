from pymsgraph.models import fields
from pymsgraph.models.base import ReadOnlyModel, PropertyModel


class Identity(ReadOnlyModel, PropertyModel):
    display_name = fields.CharField()


class IdentitySet(ReadOnlyModel, PropertyModel):
    application = fields.ModelField(Identity)
    device = fields.ModelField(Identity)
    user = fields.ModelField(Identity)


class SharePointIds(ReadOnlyModel, PropertyModel):
    """
    Graph sharepointIds resource type.

    https://learn.microsoft.com/en-us/graph/api/resources/sharepointids
    """

    list_id = fields.CharField()
    list_item_id = fields.CharField()
    list_item_unique_id = fields.CharField()
    site_id = fields.CharField()
    site_url = fields.CharField()
    tenant_id = fields.CharField()
    web_id = fields.CharField()


class ItemReference(ReadOnlyModel, PropertyModel):
    """
    Graph itemReference resource type.

    https://learn.microsoft.com/en-us/graph/api/resources/itemreference
    """

    drive_id = fields.CharField()
    drive_type = fields.CharField()
    name = fields.CharField()
    share_id = fields.CharField()
    sharepoint_ids = fields.ModelField(SharePointIds)
    site_id = fields.CharField()
    relative_path = fields.CharField(graph_attr_name="path")


class BaseItem(ReadOnlyModel):
    """
    Graph baseItem resource type.

    https://learn.microsoft.com/en-us/graph/api/resources/baseitem?view=graph-rest-1.0
    """

    created_by = fields.ModelField(IdentitySet, read_only=True)
    created_date_time = fields.DateTimeField(read_only=True)
    description = fields.CharField()
    e_tag = fields.CharField(graph_attr_name="eTag", read_only=True)
    last_modified_by = fields.ModelField(IdentitySet, read_only=True)
    last_modified_date_time = fields.DateTimeField(read_only=True)
    name = fields.CharField()
    parent_reference = fields.ModelField(ItemReference)
    web_url = fields.CharField(read_only=True)

    # Navigation properties
    created_by_user = fields.ModelField("User", read_only=True)
    last_modified_by_user = fields.ModelField("User", read_only=True)


class SiteCollection(ReadOnlyModel, PropertyModel):
    """
    Graph siteCollection resource type.

    https://learn.microsoft.com/en-us/graph/api/resources/sitecollection
    """

    archival_details = fields.Field(read_only=True)
    data_location_code = fields.CharField(read_only=True)
    hostname = fields.CharField(read_only=True)
    root = fields.Field(read_only=True)
