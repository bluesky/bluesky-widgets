from ..utils.list import EventedList


class RunList(EventedList):
    """
    A list of BlueskyRuns.
    """
    __slots__ = ()

    def __contains__(self, run):
        uid = run.metadata["start"]["uid"]
        for run_ in self:
            if run_.metadata["start"]["uid"] == uid:
                return True
        else:
            return False


def run_is_completed(run):
    "True is Run is completed and no further updates are coming."
    return run.metadata["stop"] is not None


def run_is_live_and_not_completed(run):
    "True if Run is 'live' (observable) and not yet complete."
    return hasattr(run, "events") and (not run_is_completed(run))
