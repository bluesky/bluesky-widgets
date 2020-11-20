from ..utils.list import EventedList


class RunList(EventedList):
    """
    A list of BlueskyRuns currently displayed in the Viewer.
    """

    def __contains__(self, run):
        uid = run.metadata["start"]["uid"]
        for run_ in self:
            if run_.metadata["start"]["uid"] == uid:
                return True
        else:
            return False
