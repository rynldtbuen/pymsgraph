from typing import Any
from pymsgraph.resources import Resource, R


class DirectoryObjects(Resource):

    ITEM_CLASS = "DirectoryObject"

    @property
    def relative_url(self) -> str:
        return "/directoryObjects"

    def by_id(self, dir_obj_id: str) -> "DirectoryObject":
        return DirectoryObject(self._client, parent=self, dir_obj_id=dir_obj_id)


class DirectoryObject(Resource):

    class Reference(Resource):
        @property
        def relative_url(self) -> str:
            return "/$ref"

    @property
    def relative_url(self) -> str:
        return f"/{self._dir_obj_id}"

    @property
    def ref(self) -> "Reference":
        return self.Reference(self._client, parent=self)

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        dir_obj_id = kwargs.get("dir_obj_id")
        if dir_obj_id is None:
            raise ValueError("Parameter is required, 'dir_obj_id'")
        self._dir_obj_id = dir_obj_id
