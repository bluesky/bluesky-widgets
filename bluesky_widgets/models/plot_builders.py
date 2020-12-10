from collections import defaultdict
import collections.abc
import functools
import itertools

import numpy

from .plot_specs import (
    FigureSpec,
    AxesSpec,
    ImageSpec,
    LineSpec,
    FigureSpecList,
)
from ._heuristics import infer_lines_to_plot
from .utils import auto_label, call_or_eval, RunList, run_is_live_and_not_completed
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

    def add_run(self, run):
        """
        Add a Run.

        Parameters
        ----------
        run : BlueskyRun
        """
        self.runs.append(run)

    def discard_run(self, run):
        """
        Discard a Run.

        If the Run is not present, this will return silently.

        Parameters
        ----------
        run : BlueskyRun
        """
        if run in self.runs:
            self.runs.remove(run)

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

    This supports plotting columns like ``"I0"`` but also Python
    expressions like ``"5 * log(I0/It)"`` and even
    ``"my_custom_function(I0)"``. See examples below. Consult
    :func:``bluesky_widgets.models.utils.construct_namespace` for details
    about the available variables.

    Parameters
    ----------
    max_runs : Integer
        Number of lines to show at once
    x : String | Callable
        Field name (e.g. "theta") or expression (e.g. "- deg2rad(theta) / 2")
        or callable with expected signature::

            f(run: BlueskyRun) -> x: Array

        Other signatures are also supported to allow for a somewhat "magical"
        usage. See examples below, and also see
        :func:`bluesky_widgets.models.utils.call_or_eval` for details and more
        examples.

    ys : List[String | Callable]
        Field name (e.g. "theta") or expression (e.g. "- deg2rad(theta) / 2")
        or callable with expected signature::

            f(run: BlueskyRun) -> y: Array

        Other signatures are also supported to allow for a somewhat "magical"
        usage. See examples below, and also see
        :func:`bluesky_widgets.models.utils.call_or_eval` for details and more
        examples.


    label_maker : Callable, optional
        Expected signature::

            f(run: BlueskyRun, y: String) -> label: String

    needs_streams : List[String], optional
        Streams referred to by x and y. Default is ``["primary"]``
    namespace : Dict, optional
        Inject additional tokens to be used in expressions for x and y
    axes : AxesSpec, optional
        If None, an axes and figure are created with default labels and titles
        derived from the ``x`` and ``y`` parameters.

    Attributes
    ----------
    max_runs : int
        Number of Runs to plot at once. This may be changed at any point.
        (Note: Increasing it will not restore any Runs that have already been
        removed, but it will allow more new Runs to be added.)
    runs : RunList[BlueskyRun]
        As runs are appended entries will be removed from the beginning of the
        last (first in, first out) so that there are at most ``max_runs``.
    pinned : Frozenset[String]
        Run uids of pinned runs.
    figure : FigureSpec
    axes : AxesSpec
    x : String | Callable
        Read-only access to x
    ys : Tuple[String | Callable]
        Read-only access to ys
    needs_streams : Tuple[String]
        Read-only access to stream names needed
    namespace : Dict
        Read-only access to user-provided namespace

    Examples
    --------

    Plot "det" vs "motor" and view it.

    >>> model = RecentLines(3, "motor", ["det"])
    >>> from bluesky_widgets.jupyter.figures import JupyterFigure
    >>> view = JupyterFigure(model.figure)
    >>> model.add_run(run)
    >>> model.add_run(another_run, pinned=True)

    Plot a mathematical transformation of the columns using any object in
    numpy. This can be given as a string expression:

    >>> model = RecentLines(3, "abs(motor)", ["-log(det)"])
    >>> model = RecentLines(3, "abs(motor)", ["pi * det"])
    >>> model = RecentLines(3, "abs(motor)", ["sqrt(det)"])

    Plot multiple lines.

    >>> model = RecentLines(3, "motor", ["log(I0/It)", "log(I0)", "log(It)"])

    Plot every tenth point.

    >>> model = RecentLines(3, "motor", ["intesnity[::10]"])

    Access data outside the "primary" stream, such as a stream name "baseline".

    >>> model = RecentLines(3, "motor", ["intensity/baseline['intensity'][0]"])

    As shown, objects from numpy can be used in expressions. You may define
    additional words, such as "savlog" for a Savitzky-Golay smoothing filter,
    by passing it a dict mapping the new word to the new object.

    >>> import scipy.signal
    >>> namespace = {"savgol": scipy.signal.savgol_filter}
    >>> model = RecentLines(3, "motor", ["savgol(intensity, 5, 2)"],
    ...                     namespace=namespace)

    Or you may pass in a function. It will be passed parameters according to
    their names.

    >>> model = RecentLines(3, "motor", [lambda intensity: savgol(intensity, 5, 2)])

    More examples of this function-based usage:

    >>> model = RecentLines(3, "abs(motor)", [lambda det: -log(det)])
    >>> model = RecentLines(3, "abs(motor)", [lambda det, pi: pi * det])
    >>> model = RecentLines(3, "abs(motor)", [lambda det, np: np.sqrt(det)])

    Custom, user-defined objects may be added in the same way, either by adding
    names to the namespace or providing the functions directly.
    """

    def __init__(
        self,
        max_runs,
        x,
        ys,
        *,
        label_maker=None,
        needs_streams=("primary",),
        namespace=None,
        axes=None,
    ):
        super().__init__()

        if label_maker is None:
            # scan_id is always generated by RunEngine but not stricter required by
            # the schema, so we fail gracefully if it is missing.

            if len(ys) > 1:

                def label_maker(run, y):
                    return (
                        f"Scan {run.metadata['start'].get('scan_id', '?')} "
                        f"{auto_label(y)}"
                    )

            else:

                def label_maker(run, y):
                    return f"Scan {run.metadata['start'].get('scan_id', '?')}"

        # Stash these and expose them as read-only properties.
        self._max_runs = int(max_runs)
        self._x = x
        if isinstance(ys, str):
            raise ValueError("`ys` must be a list of strings, not a string")
        self._ys = tuple(ys)
        self._label_maker = label_maker
        self._needs_streams = tuple(needs_streams)
        self._namespace = namespace

        self.runs = RunList()
        self._pinned = set()

        self._color_cycle = itertools.cycle(f"C{i}" for i in range(10))
        # Maps Run (uid) to set of LineSpec UUIDs.
        self._runs_to_lines = defaultdict(set)

        self.runs.events.added.connect(self._on_run_added)
        self.runs.events.removed.connect(self._on_run_removed)

        if axes is None:
            axes = AxesSpec(
                x_label=auto_label(self.x),
                y_label=", ".join(auto_label(y) for y in self.ys),
            )
            figure = FigureSpec((axes,), title=f"{axes.y_label} v {axes.x_label}")
        else:
            figure = axes.figure
        self.axes = axes
        self.figure = figure

    def _transform(self, run, x, y):
        return call_or_eval((x, y), run, self.needs_streams, self.namespace)

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

    def _add_lines(self, run):
        "Add a line."
        # Create a plot if we do not have one.
        # If necessary, removes runs to make room for the new one.
        self._cull_runs()

        for y in self.ys:
            label = self._label_maker(run, y)
            # If run is in progress, give it a special color so it stands out.
            if run_is_live_and_not_completed(run):
                color = "black"
                # Later, when it completes, flip the color to one from the cycle.
                run.events.completed.connect(self._on_run_complete)
            else:
                color = next(self._color_cycle)
            style = {"color": color}

            # Style pinned runs differently.
            if run.metadata["start"]["uid"] in self._pinned:
                style.update(linestyle="dashed")
                label += " (pinned)"

            func = functools.partial(self._transform, x=self.x, y=y)
            line = LineSpec(func, run, label, style)
            run_uid = run.metadata["start"]["uid"]
            self._runs_to_lines[run_uid].add(line.uuid)
            self.axes.lines.append(line)

    def _cull_runs(self):
        "Remove Runs from the beginning of self.runs to keep the length <= max_runs."
        i = 0
        while len(self.runs) > self.max_runs + len(self._pinned):
            while self.runs[i].metadata["start"]["uid"] in self._pinned:
                i += 1
            self.runs.pop(i)

    def _on_run_added(self, event):
        "When a new Run is added, draw a line or schedule it to be drawn."
        run = event.item
        # If the stream of interest is defined already, plot now.
        if set(self.needs_streams).issubset(set(list(run))):
            self._add_lines(run)
        else:
            # Otherwise, connect a callback to run when the stream of interest arrives.
            run.events.new_stream.connect(self._on_new_stream)

    def _on_run_removed(self, event):
        "Remove the line if its corresponding Run is removed."
        run_uid = event.item.metadata["start"]["uid"]
        self._pinned.discard(run_uid)
        line_uuids = self._runs_to_lines.pop(run_uid)
        for line_uuid in line_uuids:
            try:
                line = self.axes.by_uuid[line_uuid]
            except KeyError:
                # The LineSpec was externally removed from the AxesSpec.
                continue
            self.axes.lines.remove(line)

    def _on_new_stream(self, event):
        "This callback runs whenever BlueskyRun has a new stream."
        if set(self.needs_streams).issubset(set(list(event.run))):
            self._add_lines(event.run)
            event.run.events.new_stream.disconnect(self._on_new_stream)

    def _on_run_complete(self, event):
        "When a run completes, update the color from back to a color."
        run_uid = event.run.metadata["start"]["uid"]
        try:
            line_uuids = self._runs_to_lines[run_uid]
        except KeyError:
            # The Run has been removed before the Run completed.
            return
        for line_uuid in line_uuids:
            try:
                line = self.axes.by_uuid[line_uuid]
            except KeyError:
                # The LineSpec was externally removed from the AxesSpec.
                continue
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
    def ys(self):
        return self._ys

    @property
    def needs_streams(self):
        return self._needs_streams

    @property
    def namespace(self):
        return DictView(self._namespace or {})

    @property
    def pinned(self):
        return frozenset(self._pinned)


class AutoRecentLines:
    """
    Automatically guess useful lines to plot. Show the last N runs (per figure).

    Parameters
    ----------
    max_runs : int
        Number of Runs to plot at once, per figure

    Attributes
    ----------
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
    >>> model.add_run(run)
    >>> model.add_run(another_run, pinned=True)
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
        self.figures.events.removed.connect(self._on_figure_removed)

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
        instance = RecentLines(
            max_runs=self.max_runs, x=x, ys=[y], needs_streams=[stream_name]
        )
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
        for stream_name in run:
            self._handle_stream(run, stream_name, pinned)
        if run_is_live_and_not_completed(run):
            # Listen for additional streams.
            run.events.new_stream.connect(
                lambda event: self._handle_stream(run, event.name, pinned)
            )

    def discard_run(self, run):
        """
        Discard a Run, including any pinned and unpinned.

        If the Run is not present, this will return silently. Also,
        note that this only affect "active" plots that are currently
        receive new runs. Inactive ones will be left as they are.

        Parameters
        ----------
        run : BlueskyRun
        """
        for instance in self._key_to_instance.values():
            instance.discard_run(run)

    def _handle_stream(self, run, stream_name, pinned):
        "This examines a stream and adds this run to RecentLines instances."
        for key in infer_lines_to_plot(run, run[stream_name]):
            try:
                instance = self._key_to_instance[key]
            except KeyError:
                instance = self.new_instance_for_key(key)
            instance.add_run(run, pinned=pinned)

    def _on_figure_removed(self, event):
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


class Image:
    """
    Plot an image from a Run.

    By default, higher-dimensional data is handled by repeatedly averaging over
    the leading dimension until there are only two dimensions.

    Parameters
    ----------

    field : string
        Field name or expression
    label_maker : Callable, optional
        Expected signature::

            f(run: BlueskyRun, y: String) -> label: String

    needs_streams : List[String], optional
        Streams referred to by field. Default is ``["primary"]``
    namespace : Dict, optional
        Inject additional tokens to be used in expressions for x and y
    axes : AxesSpec, optional
        If None, an axes and figure are created with default labels and titles
        derived from the ``x`` and ``y`` parameters.

    Attributes
    ----------
    run : BlueskyRun
        The currently-viewed Run
    figure : FigureSpec
    axes : AxesSpec
    field : String
        Read-only access to field or expression
    needs_streams : List[String], optional
        Read-only access to streams referred to by field.
    namespace : Dict, optional
        Read-only access to user-provided namespace

    Examples
    --------
    >>> model = Images("ccd")
    >>> from bluesky_widgets.jupyter.figures import JupyterFigure
    >>> view = JupyterFigure(model.figure)
    >>> model.run = run
    """

    def __init__(
        self,
        field,
        *,
        label_maker=None,
        needs_streams=("primary",),
        namespace=None,
        axes=None,
    ):
        super().__init__()

        if label_maker is None:
            # scan_id is always generated by RunEngine but not stricter required by
            # the schema, so we fail gracefully if it is missing.

            def label_maker(run, field):
                md = self.run.metadata["start"]
                return (
                    f"Scan ID {md.get('scan_id', '?')}   UID {md['uid'][:8]}   "
                    f"{auto_label(field)}"
                )

        self._label_maker = label_maker

        # Stash these and expose them as read-only properties.
        self._field = field
        self._needs_streams = needs_streams
        self._namespace = namespace

        self._run = None

        if axes is None:
            axes = AxesSpec()
            figure = FigureSpec((axes,), title="")
        else:
            figure = axes.figure
        self.axes = axes
        self.figure = figure

    @property
    def run(self):
        return self._run

    @run.setter
    def run(self, value):
        self._run = value
        self.axes.images.clear()
        if self._run is not None:
            self._add_image()

    def _add_image(self):
        func = functools.partial(self._transform, field=self.field)
        image = ImageSpec(func, self.run, label=self.field)
        self.axes.images.append(image)
        self.axes.title = self._label_maker(self.run, self.field)
        # TODO Set axes x, y from xarray dims

    def _transform(self, run, field):
        (data,) = numpy.asarray(
            call_or_eval((field,), run, self.needs_streams, self.namespace)
        )
        # Reduce the data until it is 2D by repeatedly averaging over
        # the leading axis until there only two axes.
        while data.ndim > 2:
            data = data.mean(0)
        return data

    @property
    def needs_streams(self):
        return self._needs_streams

    @property
    def namespace(self):
        return DictView(self._namespace or {})

    @property
    def field(self):
        return self._field
