from ..utils.event import Event, EmitterGroup


class RunTree:
    """
    Tree viewer for the metadata in a BlueskyRun.

    Parameters
    ----------
    run: BlueskyRun or None, optional

    """

    def __init__(self, run=None):
        # This is a very light model. It only has one piece of state and one
        # signal when that state changes.
        self._run = run
        self.events = EmitterGroup(source=self, run=Event)

    @property
    def run(self):
        "The currently-viewed Run. (None if empty.)"
        return self._run

    @run.setter
    def run(self, run):
        self._run = run
        self.events.run(run=run)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.run!r})"
