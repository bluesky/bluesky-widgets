from collections import defaultdict
import collections.abc
import functools
import itertools
import weakref

from .plot_specs import (
    FigureSpec,
    AxesSpec,
    LineSpec,
    FigureSpecList,
)
from .utils import RunList, run_is_live_and_not_completed
from ..utils.list import EventedList
from ..utils.dict_view import DictView


class BuilderList(EventedList):
    "A list of functions that accept a BlueskyRun and return FigureSpec(s)."
    ...


class PromptPlotter:
    """
    Produce Figures from BlueskyRuns promptly (as Run completion time).

    Parameters
    ----------
    builders : BuilderList[callable]
        A list of functions that accept a BlueskyRun and return FigureSpec(s).

    Attributes
    ----------
    runs : RunList[BlueskyRun]
        Add or remove runs from this list.
    figures : FigureSpecList[FigureSpec]
        Figures will be added to this list.
    builders : BuilderList[callable]
        A list of functions with the expected signature::

            f(run: BlueskyRun) -> FigureSpec

        or::

            f(run: BlueskyRun) -> List{FigureSpec]
    """

    def __init__(self, builders):
        self.figures = FigureSpecList()
        self.builders = BuilderList()
        self.runs = RunList()
        self.builders.extend(builders)
        self.runs.events.added.connect(self._on_run_added)

    def _on_run_added(self, event):
        run = event.item
        # If Run is complete, process is now. Otherwise, schedule it to
        # process when it completes.
        if not run_is_live_and_not_completed(run):
            self._process_run(run)
        else:
            run.events.completed.connect(lambda event: self._process_run(event.run))

    def _on_builder_added(self, event):
        builder = event.item
        self.builders.append(builder)
        # Process all runs we already have with the new builder.
        for run in self.runs:
            if not run_is_live_and_not_completed(run):
                self._process_run(run)
            else:
                run.events.completed.connect(lambda event: self._process_run(event.run))

    def _process_run(self, run):
        for builder in self.builders:
            figures = builder(run)
        # Tolerate a FigureSpec or a list of them.
        if not isinstance(figures, collections.abc.Iterable):
            figures = [figures]
        self.figures.extend(figures)


def prompt_line_builder(run):
    """
    This is a simple example.

    This makes a hard-coded assumption that the data has columns "motor" and
    "det" in the primary stream.
    """

    def func(run):
        "Return any arrays x, y. They must be of equal length."
        # *Lazily* read the data so that large arrays are not loaded unless
        # the yare used.
        ds = run.primary.read()
        # Do any computation you want in here....
        return ds["motor"], ds["det"]

    label = f"Scan {run.metadata['start']['scan_id']}"
    line = LineSpec(func, run, label)
    axes = AxesSpec(lines=[line], x_label="motor", y_label="det")
    figure = FigureSpec((axes,), title="det v motor")

    return [figure]



class RecentLines:
    """
    Plot y vs x for the last N runs.

    Parameters
    ----------
    max_runs : int
        Number of lines to show at once
    x : string
        Field name
    y : string
        Field name
    stream_name : string, optional
        Stream where fields x and y are found. Default is "primary".
    func : callable, optional
        Expected signature::

            func(run: BlueskyRun, stream_name: str, x: str, y: str) -> x: Array, y: Array

    axes : AxesSpec, optional
        If None, an axes and figure are created with default labels and titles.

    Attributes
    ----------
    max_runs : int
        Number of Runs to plot at once. This may be changed at any point.
        (Note: Increasing it will not restore any Runs that have already been
        removed, but it will allow more new Runs to be added.)
    runs : RunList[BlueskyRun]
        As runs are appended entries will be removed from the beginning of the
        last (first in, first out) so that there are at most ``max_runs``.
    pinned_runs : RunList[BlueskyRun]
        These runs will not be automatically removed.
    figure : FigureSpec
    axes : AxesSpec
    x : string
        Read-only access to x field name
    y : string
        Read-only access to y field name
    stream_name : string
        Read-only access to stream name

    Examples
    --------
    >>> model = RecentLines(3, "motor", "det")
    >>> from bluesky_widgets.jupyter.figures import JupyterFigure
    >>> view = JupyterFigure(model.figure)
    >>> model.pinned_runs.append(run)

    """

    def __init__(self, max_runs, x, y, stream_name="primary", func=None, axes=None):
        super().__init__()

        if func is None:

            def func(run, stream_name, x, y):
                ds = run[stream_name].to_dask()
                return ds[x], ds[y]

        # Stash these and expose them as read-only properties.
        self._max_runs = int(max_runs)
        self._x = x
        self._y = y
        self._stream_name = stream_name
        self._func = func

        self.runs = RunList()
        self.pinned_runs = RunList()

        self._color_cycle = itertools.cycle(f"C{i}" for i in range(10))
        # Maps Run (uid) to LineSpec
        self._runs_to_lines = weakref.WeakValueDictionary()

        self.runs.events.added.connect(self._on_run_added)
        self.runs.events.removed.connect(self._on_run_removed)
        self.pinned_runs.events.added.connect(self._on_run_added)
        self.pinned_runs.events.removed.connect(self._on_run_removed)

        if axes is None:
            axes = AxesSpec(x_label=self.x, y_label=self.y)
            figure = FigureSpec((axes,), title=f"{self.y} v {self.x}")
        else:
            figure = axes.figure
        self.axes = axes
        self.figure = figure

    def add_run(self, run, pinned=False):
        """
        Add a Run.

        Parameters
        ----------
        run : BlueskyRun
        pinned : Boolean
            If True, retain this Run until it is removed by the user.
        """
        if pinned:
            self.pinned_runs.append(run)
        else:
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
        if run in self.pinned_runs:
            self.runs.remove(run)

    def _add_line(self, run):
        "Add a line."
        # Create a plot if we do not have one.
        # If necessary, removes runs to make room for the new one.
        self._cull_runs()

        label = f"Scan {run.metadata['start']['scan_id']}"
        # If run is in progress, give it a special color so it stands out.
        if run_is_live_and_not_completed(run):
            color = "black"
            # Later, when it completes, flip the color to one from the cycle.
            run.events.completed.connect(self._on_run_complete)
        else:
            color = next(self._color_cycle)
        style = {"color": color}

        # Style pinned runs differently.
        if run in self.pinned_runs:
            style.update(linestyle="dashed")
            label += " (pinned)"

        func = functools.partial(
            self.func, stream_name=self.stream_name, x=self.x, y=self.y
        )
        line = LineSpec(func, run, label, style)
        run_uid = run.metadata["start"]["uid"]
        self._runs_to_lines[run_uid] = line
        self.axes.lines.append(line)

    def _cull_runs(self):
        "Remove Runs from the beginning of self.runs to keep the length <= max_runs."
        while len(self.runs) > self.max_runs:
            self.runs.pop(0)

    def _on_run_added(self, event):
        "When a new Run is added, draw a line or schedule it to be drawn."
        run = event.item
        # If the stream of interest is defined already, plot now.
        if self.stream_name in run:
            self._add_line(run)
        else:
            # Otherwise, connect a callback to run when the stream of interest arrives.
            run.events.new_stream.connect(self._on_new_stream)

    def _on_run_removed(self, event):
        "Remove the line if its corresponding Run is removed."
        run_uid = event.item.metadata["start"]["uid"]
        try:
            line = self._runs_to_lines[run_uid]
        except KeyError:
            # The line has been removed before the Run was.
            return
        try:
            self.axes.lines.remove(line)
        except ValueError:
            # The line has been removed before the Run was.
            pass

    def _on_new_stream(self, event):
        "This callback runs whenever BlueskyRun has a new stream."
        if event.name == self.stream_name:
            self._add_line(event.run)
            event.run.events.new_stream.disconnect(self._on_new_stream)

    def _on_run_complete(self, event):
        "When a run completes, update the color from back to a color."
        run_uid = event.run.metadata["start"]["uid"]
        try:
            line = self._runs_to_lines[run_uid]
        except KeyError:
            # The line has been removed before the Run completed.
            return
        line.style.update({"color": next(self._color_cycle)})

    @property
    def max_runs(self):
        return self._max_runs

    @max_runs.setter
    def max_runs(self, value):
        self._max_runs = value
        self._cull_runs()

    # Read-only properties so that these settings are inspectable, but not
    # changeable.

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def stream_name(self):
        return self._stream_name

    @property
    def func(self):
        return self._func


def infer_lines(stream):
    "A temporary stand-in for the hints-parsing logic in BestEffortCallback."
    return [(("motor", "det"), "primary")]


class BEC:
    ...


# class AutoRecentLines(Auto):
#     class_ = RecentLines
#     init_kwargs = ...
#     default_heuristic = infer_lines


class AutoRecentLines:
    """
    Automatically guess useful lines to plot. Show the last N runs (per figure).

    Parameters
    ----------
    max_runs : int
        Number of Runs to plot at once, per figure

    Attributes
    ----------
    runs : RunList[BlueskyRun]
        As runs are appended entries will be removed from the beginning of the
        last (first in, first out) so that there are at most ``max_runs``.
    pinned_runs : RunList[BlueskyRun]
        These runs will not be automatically removed.
    figures : FigureSpecList[FigureSpec]
    max_runs : int
        Number of Runs to plot at once. This may be changed at any point.
        (Note: Increasing it will not restore any Runs that have already been
        removed, but it will allow more new Runs to be added.)
    keys_to_figures : dict
        Read-only mapping of each key to the active RecentLines instance.

    Examples
    --------
    >>> model = AutoRecentLines(3)
    >>> from bluesky_widgets.jupyter.figures import JupyterFigures
    >>> view = JupyterFigures(model.figures)
    >>> model.pinned_runs.append(run)
    """

    def __init__(self, max_runs):
        self.figures = FigureSpecList()
        self._max_runs = max_runs

        # Map key like ((x, y), stream_name) to RecentLines instance so configured.
        self._key_to_instance = {}
        # Map FigureSpec UUID to key like ((x, y), stream_name)
        self._figure_to_key = {}
        # Track inactive instances/figures which are no longer being updated
        # with new Runs. Structure is a dict-of-dicts like:
        # {key: {figure_uuid: instance, ...}, ...}
        self._inactive_instances = defaultdict(dict)
        self.runs.events.added.connect(self._on_run_added)
        self.pinned_runs.events.added.connect(self._on_run_added)
        self.figures.events.removed.connect(self._on_figure_removed_from_us)

    @property
    def keys_to_figures(self):
        "Read-only mapping of each key to the active RecentLines instance."
        return DictView({v: k for k, v in self._figure_to_key.items()})

    def new_instance_for_key(self, key):
        """
        Make a new RecentLine instance for a key.

        If there is an existing one the instance and figure will remain but
        will no longer be updated with new Runs. Those will go to a new
        instance and figure, created here.
        """
        (x, y), stream_name = key
        old_instance = self._key_to_instance.pop(key, None)
        if old_instance is not None:
            self._inactive_instances[key][old_instance.figure.uuid] = old_instance
        instance = RecentLines(x, y, self.max_runs, stream_name)
        self._key_to_instance[key] = instance
        self._figure_to_key[instance.figure.uuid] = key
        self.figures.append(instance.figure)
        return instance

    def add_run(self, run, pinned=False):
        """
        Add a Run.

        Parameters
        ----------
        run : BlueskyRun
        pinned : Boolean
            If True, retain this Run until it is removed by the user.
        """
        if pinned:
            self.pinned_runs.append(run)
        else:
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
        if run in self.pinned_runs:
            self.runs.remove(run)

    def _on_run_added(self, event):
        run = event.item
        for stream_name in run:
            self._handle_stream(run, stream_name)
        if not run_is_live_and_not_completed(run):
            # We are done with this Run.
            # We have either passed it down to RecentLines instance(s) or found
            # nothing we know to do with it.
            # HACK!
            if run in self.pinned_runs:
                self.pinned_runs.remove(run)
            else:
                self.runs.remove(run)
        else:
            # Listen for additional streams.
            run.events.new_stream.connect(self._on_new_stream)
            run.events.completed.connect(lambda event: self.runs.remove(event.run))

    def _on_new_stream(self, event):
        "This callback runs whenever BlueskyRun has a new stream."
        self._handle_stream(event.run, event.name)

    def _handle_stream(self, run, stream_name):
        "This examines a stream and adds this run to RecentLines instances."
        for key in infer_lines(run[stream_name]):
            try:
                instance = self._key_to_instance[key]
            except KeyError:
                instance = self.new_instance_for_key(key)
            if run in self.pinned_runs:
                instance.pinned_runs.append(run)
            else:
                instance.runs.append(run)

    def _on_figure_removed_from_us(self, event):
        """
        A figure was removed from self.figures.

        Remove the relevant RecentLines instance.
        """
        figure = event.item
        try:
            key = self._figure_to_key.pop(figure.uuid)
        except KeyError:
            # This figure belongs to an inactive instance.
            del self._inactive_instances[key][figure.uuid]

        else:
            self._key_to_instance.pop(key)

    @property
    def max_runs(self):
        return self._max_runs

    @max_runs.setter
    def max_runs(self, value):
        self._max_runs = value
        for instance in self._key_to_instance.values():
            instance.max_runs = value
