from typing import TYPE_CHECKING, Any, Iterable

from .directory_objects import DirectoryObject as do
from .fields import BooleanField, CharField
from .resources import MultiValuedResource, SingleValuedResource

if TYPE_CHECKING:
    from .users import User


class Groups(MultiValuedResource["Group"]):

    class RequestQueryParam(MultiValuedResource.RequestQueryParam):
        TOP = True
        SEARCH = True
        COUNT = True

    ITEM_CLASS = "Group"

    @property
    def relative_url(self):
        return "/groups"

    def by_id(self, group_id: str) -> "Group":
        return Group(self._client, parent=self, group_id=group_id)


class Group(SingleValuedResource):

    id = CharField()
    description = CharField()
    display_name = CharField()
    mail_enabled = BooleanField()
    security_enabled = BooleanField()
    mail = CharField()
    mail_nickname = CharField()
    group_type = CharField()

    @property
    def relative_url(self) -> str:
        return f"/{self._group_id}"

    @property
    def members(self) -> "Members":
        return Members(self._client, parent=self)

    def _set_kwargs(self, kwargs: dict[str, Any]):
        group_id = kwargs.get("group_id") or self.id
        if group_id is None:
            raise ValueError("Argument is required, 'group_id'")
        self._group_id = group_id


class DirectoryObject(do):

    class Reference(do.Reference):
        class RequestMethod(do.Reference.RequestMethod):
            DELETE = True


class Members(MultiValuedResource["User"]):

    class Reference(do.Reference):
        class RequestMethod(do.Reference.RequestMethod):
            POST = True

        def get_payload_from_arg(self, dir_obj_id: str):
            return {"@odata.id": self._client.directory_objects.by_id(dir_obj_id).url}

    class GraphUser(MultiValuedResource["User"]):
        ITEM_CLASS = "User"

        class RequestQueryParam(MultiValuedResource.RequestQueryParam):
            TOP = True
            SEARCH = True
            COUNT = True

        @property
        def relative_url(self):
            return f"/microsoft.graph.user"

        def get_payload_from_arg(self, dir_obj_id: str):
            return {"@odata.id": self._client.directory_objects.by_id(dir_obj_id).url}

    ITEM_CLASS = "User"

    @property
    def relative_url(self):
        return f"/members"

    @property
    def ref(self):
        return self.Reference(self._client, parent=self)

    @property
    def graph_user(self):
        return self.GraphUser(self._client, parent=self)

    def by_directory_object_id(self, dir_obj_id: str) -> DirectoryObject:
        return DirectoryObject(self._client, parent=self, dir_obj_id=dir_obj_id)

    def add(self, user_ids: str | Iterable[str]):
        pass
