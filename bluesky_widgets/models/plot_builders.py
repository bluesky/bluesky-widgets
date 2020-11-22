import collections.abc
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
    line = LineSpec(func, run, {"label": label})
    axes = AxesSpec(lines=[line], x_label="motor", y_label="det")
    figure = FigureSpec((axes,), title="det v motor")

    return [figure]


# This is matplotlib's default color cycle, obtained via
# plt.rcParams['axes.prop_cycle'].by_key()['color']
DEFAULT_COLOR_CYCLE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


class LastNLines:
    """
    Plot y vs x for the last N runs.

    Parameters
    ----------
    x : string
        Field name
    y : string
        Field name
    N : int
        Number of lines to show at once
    stream_name : string, optional
        Stream where fields x and y are found. Default is "primary".
    axes : AxesSpec, optional
        If None, an axes and figure are created with default labels and titles.

    Attributes
    ----------
    runs : RunList[BlueskyRun]
        As runs are appended entries will be removed from the beginning of the
        last (first in, first out) so that there are at most N.
    pinned_runs : RunList[BlueskyRun]
        These runs will not be automatically removed.
    figure : FigureSpec
    axes : AxesSpec
    N : int
        Number of lines to show at once. This may be changed at any point.
        (Note: Increasing it will not restore any Runs that have already been
        removed, but it will allow more new Runs to be added.)
    x : string
        Read-only access to x field name
    y : string
        Read-only access to y field name
    stream_name : string
        Read-only access to stream name

    Examples
    --------
    >>> model = LastNLines("motor", "det", 3)
    >>> from bluesky_widgets.jupyter.figures import JupyterFigure
    >>> view = JupyterFigure(model.figure)
    >>> model.pinned_runs.append(run)

    """

    def __init__(self, x, y, N, stream_name="primary", axes=None):
        super().__init__()
        # Stash these and expose them as read-only properties.
        self._N = int(N)
        self._x = x
        self._y = y
        self._stream_name = stream_name

        self.runs = RunList()
        self.pinned_runs = RunList()

        self._color_cycle = itertools.cycle(DEFAULT_COLOR_CYCLE)
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

    def _add_line(self, run):
        "Add a line."
        # Create a plot if we do not have one.
        # If necessary, removes runs to make room for the new one.
        self._cull_runs()

        stream_name = self.stream_name
        x = self.x
        y = self.y

        def func(run):
            # *Lazily* read the data so that large arrays are not loaded unless
            # the yare used.
            ds = run[stream_name].to_dask()
            return ds[x], ds[y]

        label = f"Scan {run.metadata['start']['scan_id']}"
        # If run is in progress, give it a special color so it stands out.
        if run_is_live_and_not_completed(run):
            color = "black"
            # Later, when it completes, flip the color to one from the cycle.
            run.events.completed.connect(self._on_run_complete)
        else:
            color = next(self._color_cycle)
        artist_kwargs = {"label": label, "color": color}

        # Style pinned runs differently.
        if run in self.pinned_runs:
            artist_kwargs.update(linestyle="dashed", label=label + " (pinned)")

        line = LineSpec(func, run, artist_kwargs)
        run_uid = run.metadata["start"]["uid"]
        self._runs_to_lines[run_uid] = line
        self.axes.lines.append(line)

    def _cull_runs(self):
        "Remove Runs from the beginning of self.runs to keep the length <= N."
        while len(self.runs) > self.N:
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
        line.artist_kwargs.update({"color": next(self._color_cycle)})

    @property
    def N(self):
        return self._N

    @N.setter
    def N(self, value):
        self._N = value
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


def infer_lines(stream):
    "A temporary stand-in for the hints-parsing logic in BestEffortCallback."
    return [(("motor", "det"), "primary")]


class AutoLastNLines:
    """
    Automatically guess useful lines to plot. Show the last N runs (per figure).

    Parameters
    ----------
    N : int
        number of lines to show at once

    Attributes
    ----------
    runs : RunList[BlueskyRun]
        As runs are appended entries will be popped off the beginning of the last
        (first in, first out) so that there are at most N.
    pinned_runs : RunList[BlueskyRun]
        These runs will not be popped.
    figures : FigureSpecList[FigureSpec]
    """

    def __init__(self, N):
        self.figures = FigureSpecList()
        self.runs = RunList()
        self.pinned_runs = RunList()
        self._N = N

        # Map ((x, y), stream_name) to LastNLines instances so configured.
        self._instances = {}
        self.runs.events.added.connect(self._on_run_added)
        self.pinned_runs.events.added.connect(self._on_run_added)
        self.figures.events.removed.connect(self._on_figure_removed_from_us)

    def _on_run_added(self, event):
        run = event.item
        for stream_name in run:
            self._handle_stream(run, stream_name)
        if not run_is_live_and_not_completed(run):
            # We are done with this Run.
            # We have either passed it down to LastNLines instance(s) or found
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
        "This examines a stream and adds this run to LastNLines instances."
        for key in infer_lines(run[stream_name]):
            try:
                instance = self._instances[key]
            except KeyError:
                (x, y), stream_name = key
                instance = LastNLines(x, y, self._N, stream_name)
                instance.figures.events.added.connect(self._on_figure_added_by_instance)
                instance.figures.events.removed.connect(
                    self._on_figure_removed_by_instance
                )
                self._instances[key] = instance
            if run in self.pinned_runs:
                instance.pinned_runs.append(run)
            else:
                instance.runs.append(run)

    def _on_figure_added_by_instance(self, event):
        figure = event.item
        self.figures.append(figure)

    def _on_figure_removed_by_instance(self, event):
        figure = event.item
        self.figures.remove(figure)

    def _on_figure_removed_from_us(self, event):
        """
        A figure was removed from self.figures.

        Remove it from the relevant LastNLines instance.
        """
        figure = event.item
        # Find the relevant instance by brute force search. This should not
        # take too long because the serach is not a large one.
        for instance in self._instances.values():
            if figure in instance.figures:
                with instance.figures.events.removed.blocker(
                    callback=self._on_figure_removed_by_instance
                ):
                    instance.figures.remove(figure)
                break

    @property
    def N(self):
        return self._N
