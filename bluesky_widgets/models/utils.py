import numpy

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


# Make numpy functions accessible as (for example) log, np.log, and numpy.log.
_base_namespace = {"numpy": numpy, "np": numpy}
_base_namespace.update({name: getattr(numpy, name) for name in numpy.__all__})


def construct_namespace(run):
    """
    Put the contents of a run into a namespace to ``eval`` expressions in.

    This is used by the plot builders to support usages like

    >>> model = RecentLines(3, "-motor", ["log(det)"])

    The words available in these expressions include:

    * All functions in numpy. They can be spelled as ``log``, ``np.log``, or
      ``numpy.log``
    * The columns in the "primary" stream of data, as in ``"I0"``
    * All the streams, with the data accessible as items in a dict, as in
      ``"primary['It']"`` or ``"baseline['motor']"``
    * The ``BlueskyRun`` itself, as ``"run"``, from which any data or metadata
      can be obtained

    In the event of name collisions, items lower in the list above will get
    precedence.

    Parameters
    ----------
    run : BlueskyRun

    Returns
    -------
    namespace : Dict
    """
    namespace = dict(_base_namespace)  # shallow copy
    if "primary" in run:
        ds = run["primary"].to_dask()
        namespace.update({column: ds[column] for column in ds})
    namespace.update({stream_name: run[stream_name].to_dask() for stream_name in run})
    namespace.update({"run": run})
    return namespace
