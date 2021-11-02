import ast
import collections
import contextlib
import inspect

import numpy

from ..utils.list import EventedList
from ..utils.event import EmitterGroup, Event


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


def run_is_live(run):
    "True if Run is 'live' (observable) based on a streaming source, not at rest."
    return hasattr(run, "events")


def run_is_live_and_not_completed(run):
    "True if Run is 'live' (observable) and not yet complete."
    return run_is_live(run) and (not run_is_completed(run))


@contextlib.contextmanager
def lock_if_live(run):
    """
    Lock to prevent new data from being added, if this is a 'live' BlueskyRun.

    If it is a BlueskyRun backed by data at rest (i.e. from databroker) do
    nothing.
    """
    if run_is_live(run):
        with run.write_lock:
            yield
    else:
        yield


# Make numpy functions accessible as (for example) log, np.log, and numpy.log.
_base_namespace = {"numpy": numpy, "np": numpy}
_base_namespace.update({name: getattr(numpy, name) for name in numpy.__all__})


def construct_namespace(run, stream_names):
    """
    Put the contents of a run into a namespace to lookup in or ``eval`` expressions in.

    This is used by the plot builders to support usages like

    >>> model = Lines("-motor", ["log(det)"])

    The words available in these expressions include:

    * The ``BlueskyRun`` itself, as ``"run"``, from which any data or metadata
      can be obtained
    * All the streams, with the data accessible as items in a dict, as in
      ``"primary['It']"`` or ``"baseline['motor']"``
    * The columns in the streams given by stream_names, as in ``"I0"``. If a
      column name appears in multiple streams, the streams earlier in the list
      get precedence.
    * All functions in numpy. They can be spelled as ``log``, ``np.log``, or
      ``numpy.log``

    In the event of name collisions, items higher in the list above will get
    precedence.

    Parameters
    ----------
    run : BlueskyRun
    stream_names : List[String]

    Returns
    -------
    namespace : Dict
    """
    namespace = dict(_base_namespace)  # shallow copy
    with lock_if_live(run):
        run_start_time = run.metadata["start"]["time"]
        # Add columns from streams in stream_names. Earlier entries will get
        # precedence.
        for stream_name in reversed(stream_names):
            ds = run[stream_name].to_dask()
            namespace.update({column: ds[column] for column in ds})
            namespace.update({column: ds[column] for column in ds.coords})
        if "time" in namespace:
            namespace["time"] = namespace["time"] - run_start_time
        namespace.update({stream_name: run[stream_name].to_dask() for stream_name in stream_names})
        for stream_name in stream_names:
            namespace[stream_name]["time"] = namespace[stream_name]["time"] - run_start_time
    namespace.update({"run": run})
    return namespace


class BadExpression(Exception):
    pass


def call_or_eval(mapping, run, stream_names, namespace=None):
    """
    Given a mix of callables and string expressions, call or eval them.

    Parameters
    ----------
    mapping : Dict[String, String | Callable]
        Each item must be a stream name, field name, a valid Python
        expression, or a callable. The signature of the callable may include
        any valid Python identifiers provideed by :func:`construct_namespace`
        or the user-provided namespace parmeter below. See examples.
    run : BlueskyRun
    stream_names : List[String]
    namespace : Dict, optional

    Returns
    -------
    results : Dict[String, Any]

    Raises
    ------
    ValueError
        If input is not String or Callable
    BadExpression
        If input is String and eval(...) raises an error

    Examples
    --------

    A function can have access to the whole BlueskyRun.

    >>> def f(run):
    ...     ds = run.primary.read()
    ...     return (ds["a"] - ds["b"]) / (ds["a"] + ds["b"])
    ...
    >>> call_or_eval({"x": f}, run, ["primary"])

    But, it also provides a more "magical" option in support of brevity.
    The signature may include parameters with the names streams or fields. The
    names in the signature are significant and will determine what parameters
    the function is called with.

    >>> def f(a, b):
    ...     return (a - b) / (a + b)
    ...
    >>> call_or_eval({"x": f}, run, ["primary"])

    Equivalently, as a lambda function:
    >>> call_or_eval({"f": lambda a, b: (a - b) / (a + b)}, run, ["primary"])
    """
    with lock_if_live(run):
        namespace_ = construct_namespace(run, stream_names)
        # Overlay user-provided namespace.
        namespace_.update(namespace or {})
        del namespace  # Avoid conflating namespace and namespace_ below.

        return {key: call_or_eval_one(item, namespace_) for key, item in mapping.items()}


def call_or_eval_one(item, namespace):
    """
    Given a mix of callables and string expressions, call or eval them.

    Parameters
    ----------
    item : String | Callable
        Each item must be a stream name, field name, a valid Python
        expression, or a callable. The signature of the callable may include
        any valid Python identifiers provideed in the namespace.

    namespace : Dict
        The namespace that the item is evaluated against.

    Returns
    -------
    result : Any

    Raises
    ------
    ValueError
        If input is not String or Callable
    BadExpression
        If input is String and eval(...) raises an error

    """
    # If it is a callable, call it.
    if callable(item):
        # Inspect the callable's signature. For each parameter, find an
        # item in our namespace with a matching name. This is similar
        # to the "magic" of pytest fixtures.
        parameters = inspect.signature(item).parameters
        kwargs = {}
        for name, parameter in parameters.items():
            try:
                kwargs[name] = namespace[name]
            except KeyError:
                if parameter.default is parameter.empty:
                    raise ValueError(f"Cannot find match for parameter {name}")
                # Otherwise, it's an optional parameter, so skip it.
        return item(**kwargs)
    elif isinstance(item, str):
        # If it is a key in our namespace, look it up.
        try:
            # This handles field or stream names that are not valid
            # Python identifiers (e.g. ones with spaces in them).
            return namespace[item]
        except KeyError:
            pass
        # Check whether it is valid Python syntax.
        try:
            ast.parse(item)
        except SyntaxError as err:
            raise ValueError(f"Could find {item!r} in namespace or parse it as a Python expression.") from err
        # Try to evaluate it as a Python expression in the namespace.
        try:
            return eval(item, namespace)
        except Exception as err:
            raise ValueError(f"Could find {item!r} in namespace or evaluate it.") from err
    else:
        raise ValueError(f"expected callable or string, received {item!r} of type {type(item).__name__}")


def auto_label(callable_or_expr):
    """
    Given a callable or a string, extract a name for labeling axes.

    Parameters
    ----------
    callable_or_expr : String | Callable

    Returns
    -------
    label : String
    """
    if callable(callable_or_expr):
        return getattr(callable_or_expr, "__name__", repr(callable_or_expr))
    elif isinstance(callable_or_expr, str):
        return callable_or_expr
    else:
        raise ValueError(
            f"expected callable or string, received {callable_or_expr!r} of "
            f"type {type(callable_or_expr).__name__}"
        )


class RunManager:
    """
    Keep a RunList with a maximum number of Runs, plus any 'pinned' Runs.

    This is used internally as a helper class by Lines, Images, and others.
    This tracks the relationship between Runs and Artists and ensures correct
    cleanup when a Run is removed.
    """

    def __init__(self, max_runs, needs_streams):
        self._max_runs = int(max_runs)
        self._needs_streams = tuple(needs_streams)
        self.runs = RunList()
        self._pinned = set()
        # Maps Run (uid) to set of ArtistSpec.
        self._runs_to_artists = collections.defaultdict(list)

        self.runs.events.added.connect(self._on_run_added)
        self.runs.events.removed.connect(self._on_run_removed)
        self.events = EmitterGroup(source=self, run_ready=Event)

    def add_run(self, run, *, pinned=False):
        """
        Add a Run.

        Parameters
        ----------
        run : BlueskyRun
        pinned : Boolean
            If True, retain this Run until it is removed by the user.
        """
        if pinned:
            self._pinned.add(run.metadata["start"]["uid"])
        self.runs.append(run)

    def discard_run(self, run):
        """
        Discard a Run, including any pinned and unpinned.

        If the Run is not present, this will return silently.

        Parameters
        ----------
        run : BlueskyRun
        """
        if run in self.runs:
            self.runs.remove(run)

    def track_artist(self, artist, runs):
        """
        Track an Artist.

        This ensures it will be removed when the associated Run is removed.

        Parameters
        ----------
        artist : ArtistSpec
        runs : List[BlueskyRun]
        """
        # TODO Someday we will need aritsts that represent data from *multiple*
        # runs, and then we will need to rethink the expected API of artist
        # (.run -> .runs?) and the cache management here. But that would be a
        # widereaching change, so we'll stay within the framework as it is
        # today.
        if len(runs) != 1:
            raise NotImplementedError("We current assume a 1:1 association of aritsts and runs.")
        (run,) = runs
        run_uid = run.metadata["start"]["uid"]
        self._runs_to_artists[run_uid].append(artist)

    def _cull_runs(self):
        "Remove Runs from the beginning of self.runs to keep the length <= max_runs."
        i = 0
        while len(self.runs) > self.max_runs + len(self._pinned):
            while self.runs[i].metadata["start"]["uid"] in self._pinned:
                i += 1
            self.runs.pop(i)

    def _on_run_added(self, event):
        """
        When a new Run is added, mark it as ready or listen for it to become ready.

        By "ready" we mean, it has all the streams it needs to be drawn.
        """
        self._cull_runs()
        run = event.item
        if run_is_live_and_not_completed(run):
            # If the stream of interest is defined already, plot now.
            if set(self.needs_streams).issubset(set(list(run))):
                self.events.run_ready(run=run)
            else:
                # Otherwise, connect a callback to run when the stream of interest arrives.
                run.events.new_stream.connect(self._on_new_stream)
        else:
            if set(self.needs_streams).issubset(set(list(run))):
                self.events.run_ready(run=run)

    def _on_run_removed(self, event):
        "Remove any extant artists if its corresponding Run is removed."
        run_uid = event.item.metadata["start"]["uid"]
        self._pinned.discard(run_uid)
        for artist in self._runs_to_artists.pop(run_uid):
            artist.axes.discard(artist)

    def _on_new_stream(self, event):
        "When an unready Run get a new stream, check it if is now ready."
        if set(self.needs_streams).issubset(set(list(event.run))):
            self.events.run_ready(run=event.run)
            event.run.events.new_stream.disconnect(self._on_new_stream)

    @property
    def max_runs(self):
        return self._max_runs

    @max_runs.setter
    def max_runs(self, value):
        self._max_runs = value
        self._cull_runs()

    @property
    def pinned(self):
        return frozenset(self._pinned)

    @property
    def needs_streams(self):
        return self._needs_streams
