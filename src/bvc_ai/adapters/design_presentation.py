"""Presentation output is derived display data, never a geometry write API."""
from copy import deepcopy


class DesignPresentation:
    def __init__(self, store):
        self.__store = store

    def snapshot(self, task_id):
        task = self.__store.get(task_id)
        return deepcopy({"project_id": task["project_id"], "source_status": "TESTDATA",
                         "objects": task["objects"], "active_revisions": task["active_revisions"]})

    def update(self, task_id, changes):
        with self.__store.db:
            self.__store.event(task_id, "presentation", "presentation_write_denied",
                               reason="Presentatielaag is alleen-lezen; geometrie en bronstatus zijn domeindata")
        raise PermissionError("Presentatielaag mag geen ruimtelijk model of bronstatus wijzigen")
