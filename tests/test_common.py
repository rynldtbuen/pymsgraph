from pymsgraph.models.common import BaseItem


def test_baseitem_created_by_model_field():
    data = {
        "id": "item1",
        "createdBy": {"user": {"displayName": "Ada Lovelace"}},
    }

    item = BaseItem.from_graph(data)

    assert item.created_by.user.display_name == "Ada Lovelace"
