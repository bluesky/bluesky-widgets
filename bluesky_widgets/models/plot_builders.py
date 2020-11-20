import collections.abc
import itertools
import weakref

from .plot_specs import (
    FigureSpec,
    AxesSpec,
    LineSpec,
    FigureSpecList,
)
from .utils import RunList
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
        As runs are appended entries will be popped off the beginning of the last
        (first in, first out) so that there are at most N.
    figures : FigureSpecList[FigureSpec]
    builders : BuilderList[callable]
        A list of functions that accept a BlueskyRun and return FigureSpec(s).
    """

    def __init__(self, builders):
        self.figures = FigureSpecList()
        self.builders = BuilderList()
        self.runs = RunList()
        self.builders.extend(builders)
        self.runs.events.added.connect(self._on_run_added)

    def _on_run_added(self, event):
        run = event.item
        if is_completed(run):
            self._process_run(run)
        else:
            run.events.completed.connect(lambda event: self._process_run(event.run))

    def _process_run(self, run):
        for builder in self.builders:
            figure_specs = builder(run)
        # Tolerate a FigureSpec or a list of them.
        if not isinstance(figure_specs, collections.abc.Iterable):
            figure_specs = [figure_specs]
        self.figures.extend(figure_specs)


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
    line_spec = LineSpec(func, run, {"label": label})
    axes_spec = AxesSpec(lines=[line_spec], x_label="motor", y_label="det")
    figure_spec = FigureSpec((axes_spec,), title="det v motor")

    return [figure_spec]


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
        field name
    y : string
        field name
    N : int
        number of lines to show at once
    stream_name : string, optional
        Stream where fields x and y are found. Default is "primary".

    Attributes
    ----------
    runs : RunList[BlueskyRun]
        As runs are appended entries will be popped off the beginning of the last
        (first in, first out) so that there are at most N.
    pinned_runs : RunList[BlueskyRun]
        These runs will not be popped.
    figures : FigureSpecList[FigureSpec]

    Examples
    --------
    >>> model = LastNLines("motor", "det", 3)
    >>> view = JupyterFigures(model.figures)
    >>> model.pinned_runs.append(run)

    """

    def __init__(self, x, y, N, stream_name="primary"):
        super().__init__()
        # Stash these and expose them as read-only properties.
        self._N = int(N)
        self._x = x
        self._y = y
        self._stream_name = stream_name

        self.figures = FigureSpecList()
        self.runs = RunList()
        self.pinned_runs = RunList()

        self._current_figure_axes = None
        self._color_cycle = itertools.cycle(DEFAULT_COLOR_CYCLE)
        # Maps Run (uid) to LineSpec
        self._runs_to_lines = weakref.WeakValueDictionary()

        self.figures.events.removed.connect(self._on_figure_removed)
        self.runs.events.added.connect(self._on_run_added)
        self.runs.events.removed.connect(self._on_run_removed)
        self.pinned_runs.events.added.connect(self._on_run_added)
        self.pinned_runs.events.removed.connect(self._on_run_removed)

    def new_plot(self):
        "Start a new plot, leaving the current one (if any) as is."
        axes_spec = AxesSpec(x_label=self.x, y_label=self.y)
        figure_spec = FigureSpec((axes_spec,), title=f"{self.y} v {self.x}")
        self._current_figure_axes = (figure_spec, axes_spec)
        self.figures.append(figure_spec)

    def _add_line(self, run):
        "Add a line."
        # Create a plot if we do not have one.
        if self._current_figure_axes is None:
            self.new_plot()
        figure_spec, axes_spec = self._current_figure_axes
        # If necessary, removes runs to make room for the new one.
        while len(self.runs) > self.N:
            self.runs.pop(0)

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
        if run.metadata["stop"] is None:
            color = "black"
            # Later, when it completes, flip the color to one from the cycle.
            run.events.completed.connect(self._on_run_complete)
        else:
            color = next(self._color_cycle)
        artist_kwargs = {"label": label, "color": color}

        # Style pinned runs differently.
        if run in self.pinned_runs:
            artist_kwargs.update(linestyle="dashed", label=label + " (pinned)")

        line_spec = LineSpec(func, run, artist_kwargs)
        run_uid = run.metadata["start"]["uid"]
        self._runs_to_lines[run_uid] = line_spec
        axes_spec.lines.append(line_spec)

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
            line_spec = self._runs_to_lines[run_uid]
        except KeyError:
            # The line has been removed before the Run was.
            return
        axes_spec = line_spec.axes
        try:
            axes_spec.lines.remove(line_spec)
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
            line_spec = self._runs_to_lines[run_uid]
        except KeyError:
            # The line has been removed before the Run completed.
            return
        line_spec.artist_kwargs.update({"color": next(self._color_cycle)})

    def _on_figure_removed(self, event):
        "Reset self._current_figure_axes to None if the figure is removed."
        figure = event.item
        if self._current_figure_axes is not None:
            current_figure, _ = self._current_figure_axes
            if figure == current_figure:
                self._current_figure_axes = None

    # Read-only properties so that these settings are inspectable, but not
    # changeable.

    @property
    def N(self):
        return self._N

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


def is_completed(run):
    "True is Run is completed and no further updates are coming."
    return run.metadata["stop"] is not None


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

    def _on_run_added(self, event):
        run = event.item
        for stream_name in run:
            self._handle_stream(run, stream_name)
        if is_completed(run):
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
        figure_spec = event.item
        self.figures.append(figure_spec)

    def _on_figure_removed_by_instance(self, event):
        figure_spec = event.item
        self.figures.remove(figure_spec)

    @property
    def N(self):
        return self._N
