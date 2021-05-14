import collections
import functools
import itertools

import numpy

from .plot_specs import (
    Figure,
    Axes,
    Image,
    Line,
)
from .utils import auto_label, call_or_eval, RunManager, run_is_live_and_not_completed
from ..utils.dict_view import DictView
from ..utils.event import EmitterGroup, Event
from ..utils.list import EventedList


class Lines:
    """
    Plot ys vs x for the last N runs.

    This supports plotting columns like ``"I0"`` but also Python
    expressions like ``"5 * log(I0/It)"`` and even
    ``"my_custom_function(I0)"``. See examples below. Consult
    :func:`bluesky_widgets.models.utils.construct_namespace` for details
    about the available variables.

    Parameters
    ----------
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

    max_runs : Integer
        Number of Runs to visualize at once. Default is 10.

    label_maker : Callable, optional
        Expected signature::

            f(run: BlueskyRun, y: String) -> label: String

    needs_streams : List[String], optional
        Streams referred to by x and y. Default is ``["primary"]``
    namespace : Dict, optional
        Inject additional tokens to be used in expressions for x and y
    axes : Axes, optional
        If None, an axes and figure are created with default labels and titles
        derived from the ``x`` and ``y`` parameters.

    Attributes
    ----------
    max_runs : int
        Number of Runs to visualize at once. This may be changed at any point.
        (Note: Increasing it will not restore any Runs that have already been
        removed, but it will allow more new Runs to be added.) Runs added
        with ``pinned=True`` are exempt from the limit.
    runs : RunList[BlueskyRun]
        As runs are appended entries will be removed from the beginning of the
        last (first in, first out) so that there are at most ``max_runs``.
    pinned : Frozenset[String]
        Run uids of pinned runs.
    figure : Figure
    axes : Axes
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

    >>> model = Lines("motor", ["det"])
    >>> from bluesky_widgets.jupyter.figures import JupyterFigure
    >>> view = JupyterFigure(model.figure)
    >>> model.add_run(run)
    >>> model.add_run(another_run, pinned=True)

    Plot a mathematical transformation of the columns using any object in
    numpy. This can be given as a string expression:

    >>> model = Lines("abs(motor)", ["-log(det)"])
    >>> model = Lines("abs(motor)", ["pi * det"])
    >>> model = Lines("abs(motor)", ["sqrt(det)"])

    Plot multiple lines.

    >>> model = Lines("motor", ["log(I0/It)", "log(I0)", "log(It)"])

    Plot every tenth point.

    >>> model = Lines("motor", ["intesnity[::10]"])

    Access data outside the "primary" stream, such as a stream name "baseline".

    >>> model = Lines("motor", ["intensity/baseline['intensity'][0]"])

    As shown, objects from numpy can be used in expressions. You may define
    additional words, such as "savlog" for a Savitzky-Golay smoothing filter,
    by passing it a dict mapping the new word to the new object.

    >>> import scipy.signal
    >>> namespace = {"savgol": scipy.signal.savgol_filter}
    >>> model = Lines("motor", ["savgol(intensity, 5, 2)"],
    ...                     namespace=namespace)

    Or you may pass in a function. It will be passed parameters according to
    their names.

    >>> model = Lines("motor", [lambda intensity: savgol(intensity, 5, 2)])

    More examples of this function-based usage:

    >>> model = Lines("abs(motor)", [lambda det: -log(det)])
    >>> model = Lines("abs(motor)", [lambda det, pi: pi * det])
    >>> model = Lines("abs(motor)", [lambda det, np: np.sqrt(det)])

    Custom, user-defined objects may be added in the same way, either by adding
    names to the namespace or providing the functions directly.
    """

    def __init__(
        self,
        x,
        ys,
        *,
        max_runs=10,
        label_maker=None,
        needs_streams=("primary",),
        namespace=None,
        axes=None,
    ):
        super().__init__()

        if label_maker is None:
            # scan_id is always generated by RunEngine but not stricter required by
            # the schema, so we fail gracefully if it is missing.
            def label_maker(run, y):
                return f"Scan {run.metadata['start'].get('scan_id', '?')} {auto_label(y)}"

        self._x = x
        if isinstance(ys, str):
            raise ValueError("`ys` must be a list of strings, not a string")
        self._ys = EventedList(ys)
        # Maps ys to set of ArtistSpec.
        self._ys_to_artists = collections.defaultdict(list)
        self._label_maker = label_maker
        self._namespace = namespace
        if axes is None:
            axes = Axes(
                x_label=auto_label(self.x),
                y_label=", ".join(auto_label(y) for y in self.ys),
            )
            figure = Figure((axes,), title="")
        else:
            figure = axes.figure
        self.axes = axes
        if self.axes.x_label is None:
            self.axes.x_label = auto_label(self.x)
        if self.axes.y_label is None:
            self.axes.y_label = self._default_y_label()
        if self.axes.title is None:
            self.axes.title = self._default_title()
        self.figure = figure
        # If the Axes' figure is not yet set, listen for it to be set.
        if figure is None:

            def set_figure(event):
                self.figure = event.value
                # This occurs at most once, so we can now stop listening.
                self.axes.events.figure.disconnect(set_figure)

            self.axes.events.figure.connect(set_figure)

        # Keep title up to date with self.ys or leave it as user-defined value
        self._control_title = self.axes.title == self._default_title()
        # Keep y_label up to date with self.ys or leave it as user-defined value
        self._control_y_label = self.axes.y_label == self._default_y_label()

        self._color_cycle = itertools.cycle(f"C{i}" for i in range(10))

        self._run_manager = RunManager(max_runs, needs_streams)
        self._run_manager.events.run_ready.connect(self._add_lines)
        self.add_run = self._run_manager.add_run
        self.discard_run = self._run_manager.discard_run
        self.events = EmitterGroup(
            source=self,
            title=Event,
            y_label=Event,
        )

        self.ys.events.added.connect(self._add_ys)
        self.ys.events.removed.connect(self._remove_ys)

    def _default_y_label(self):
        return ", ".join(auto_label(y) for y in self.ys)

    def _default_title(self):
        return f"{self._default_y_label()} v {self.axes.x_label}"

    def _transform(self, run, x, y):
        return call_or_eval({"x": x, "y": y}, run, self.needs_streams, self.namespace)

    def _add_lines(self, event):
        "Add a line."
        if self._control_y_label:
            self.y_label = self._default_y_label()
        if self._control_title:
            self.title = self._default_title()

        run = event.run
        for y in self.ys:
            label = self._label_maker(run, y)
            # If run is in progress, give it a special color so it stands out.
            if run_is_live_and_not_completed(run):
                color = "black"

                def restyle_line_when_complete(event):
                    "When run is complete, update style."
                    line.style.update({"color": next(self._color_cycle)})

                run.events.completed.connect(restyle_line_when_complete)
            else:
                color = next(self._color_cycle)
            style = {"color": color}

            # Style pinned runs differently.
            if run.metadata["start"]["uid"] in self.pinned:
                style.update(linestyle="dashed")
                label += " (pinned)"

            func = functools.partial(self._transform, x=self.x, y=y)
            line = Line.from_run(func, run, label, style)
            self._run_manager.track_artist(line, [run])
            self.axes.artists.append(line)
            self._ys_to_artists[y].append(line)

    def _add_ys(self, event):
        "Add a y."
        # Update title and y_label when adding a new y
        if self._control_y_label:
            self.y_label = self._default_y_label()
        if self._control_title:
            self.title = self._default_title()

        y = event.item
        for run in self._run_manager.runs:
            label = self._label_maker(run, y)
            # If run is in progress, give it a special color so it stands out.
            if run_is_live_and_not_completed(run):
                color = "black"

                def restyle_line_when_complete(event):
                    "When run is complete, update style."
                    line.style.update({"color": next(self._color_cycle)})

                run.events.completed.connect(restyle_line_when_complete)
            else:
                color = next(self._color_cycle)
            style = {"color": color}

            # Style pinned runs differently.
            if run.metadata["start"]["uid"] in self.pinned:
                style.update(linestyle="dashed")
                label += " (pinned)"

            func = functools.partial(self._transform, x=self.x, y=y)
            line = Line.from_run(func, run, label, style)
            self._run_manager.track_artist(line, [run])
            self.axes.artists.append(line)
            self._ys_to_artists[y].append(line)

    def _remove_ys(self, event):
        "Remove a y."
        # Update title and y_label when removing a y
        if self._control_y_label:
            self.y_label = self._default_y_label()
        if self._control_title:
            self.title = self._default_title()
        y = event.item
        for artist in self._ys_to_artists.pop(y):
            artist.axes.discard(artist)

    @property
    def x(self):
        return self._x

    @property
    def ys(self):
        return self._ys

    @property
    def namespace(self):
        return DictView(self._namespace or {})

    # Expose some properties from the internal RunManger helper class.

    @property
    def runs(self):
        return self._run_manager.runs

    @property
    def max_runs(self):
        return self._run_manager.max_runs

    @max_runs.setter
    def max_runs(self, value):
        self._run_manager.max_runs = value

    @property
    def needs_streams(self):
        return self._run_manager._needs_streams

    @property
    def pinned(self):
        return self._run_manager._pinned

    # Expose axes title and y_label

    @property
    def title(self):
        return self.axes.title

    @title.setter
    def title(self, value):
        if value is None or value == self._default_title():
            self._control_title = True
            value = self._default_title()
        else:
            # Title has been set to something specific.
            # Don't sync it with self.ys
            self._control_title = False
        self.axes.title = value
        self.events.title(value=value)

    @property
    def y_label(self):
        return self.axes.y_label

    @y_label.setter
    def y_label(self, value):
        if value is None or value == self._default_y_label():
            self._control_y_label = True
            value = self._default_y_label()
        else:
            # y_label has been set to something specific.
            # Don't sync it with self.ys
            self._control_y_label = False
        self.axes.y_label = value
        self.events.y_label(value=value)


class Images:
    """
    Plot an image from a Run.

    By default, higher-dimensional data is handled by repeatedly averaging over
    the leading dimension until there are only two dimensions.

    Parameters
    ----------

    field : string
        Field name or expression
    max_runs : Integer
        Number of Runs to visualize at once. Default is 1.
    label_maker : Callable, optional
        Expected signature::

            f(run: BlueskyRun, y: String) -> label: String

    needs_streams : List[String], optional
        Streams referred to by field. Default is ``["primary"]``
    namespace : Dict, optional
        Inject additional tokens to be used in expressions for x and y
    axes : Axes, optional
        If None, an axes and figure are created with default labels and titles
        derived from the ``x`` and ``y`` parameters.

    Attributes
    ----------
    max_runs : int
        Number of Runs to visualize at once. This may be changed at any point.
        (Note: Increasing it will not restore any Runs that have already been
        removed, but it will allow more new Runs to be added.) Runs added
        with ``pinned=True`` are exempt from the limit.
    runs : RunList[BlueskyRun]
        As runs are appended entries will be removed from the beginning of the
        last (first in, first out) so that there are at most ``max_runs``.
    pinned : Frozenset[String]
        Run uids of pinned runs.
    figure : Figure
    axes : Axes
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
    >>> model.add_run(run)
    """

    # TODO: fix x and y limits here

    def __init__(
        self,
        field,
        *,
        max_runs=1,
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
                md = run.metadata["start"]
                return f"Scan ID {md.get('scan_id', '?')}   UID {md['uid'][:8]}   " f"{auto_label(field)}"

        self._field = field
        self._label_maker = label_maker
        self._namespace = namespace
        if axes is None:
            axes = Axes()
            figure = Figure((axes,), title="")
        else:
            figure = axes.figure
        self.axes = axes
        self.figure = figure
        # If the Axes' figure is not yet set, listen for it to be set.
        if figure is None:

            def set_figure(event):
                self.figure = event.value
                # This occurs at most once, so we can now stop listening.
                self.axes.events.figure.disconnect(set_figure)

            self.axes.events.figure.connect(set_figure)

        self._run_manager = RunManager(max_runs, needs_streams)
        self._run_manager.events.run_ready.connect(self._add_images)
        self.add_run = self._run_manager.add_run
        self.discard_run = self._run_manager.discard_run

    def _add_images(self, event):
        run = event.run
        func = functools.partial(self._transform, field=self.field)
        image = Image.from_run(func, run, label=self.field)
        self._run_manager.track_artist(image, [run])
        self.axes.artists.append(image)
        self.axes.title = self._label_maker(run, self.field)
        # TODO Set axes x, y from xarray dims

    def _transform(self, run, field):
        result = call_or_eval({"array": field}, run, self.needs_streams, self.namespace)
        # If the data is more than 2D, take the middle slice from the leading
        # axis until there are only two axes.
        data = result["array"]
        while data.ndim > 2:
            if data.shape[0] == 0:
                # Handle case where array is just initialized, with a shape like (0, y, x).
                data = numpy.zeros(data.shape[1:])
                continue
            middle = data.shape[0] // 2
            data = data[middle]
        result["array"] = data
        return result

    @property
    def field(self):
        return self._field

    @property
    def namespace(self):
        return DictView(self._namespace or {})

    # Expose some properties from the internal RunManger helper class.

    @property
    def runs(self):
        return self._run_manager.runs

    @property
    def max_runs(self):
        return self._run_manager.max_runs

    @max_runs.setter
    def max_runs(self, value):
        self._run_manager.max_runs = value

    @property
    def needs_streams(self):
        return self._run_manager._needs_streams

    @property
    def pinned(self):
        return self._run_manager._pinned


class RasteredImages:
    """
    Plot a rastered image from a Run.

    Parameters
    ----------

    field : string
        Field name or expression
    shape : Tuple[Integer]
        The (row, col) shape of the raster
    label_maker : Callable, optional
        Expected signature::

            f(run: BlueskyRun, y: String) -> label: String

    needs_streams : List[String], optional
        Streams referred to by field. Default is ``["primary"]``
    namespace : Dict, optional
        Inject additional tokens to be used in expressions for x and y
    axes : Axes, optional
        If None, an axes and figure are created with default labels and titles
        derived from the ``x`` and ``y`` parameters.
    clim : Tuple, optional
        The color limits
    cmap : String or Colormap, optional
        The color map to use
    extent : scalars (left, right, bottom, top), optional
        Passed through to :meth:`matplotlib.axes.Axes.imshow`
    x_positive : String, optional
        Defines the positive direction of the x axis, takes the values 'right'
        (default) or 'left'.
    y_positive : String, optional
        Defines the positive direction of the y axis, takes the values 'up'
        (default) or 'down'.

    Attributes
    ----------
    run : BlueskyRun
        The currently-viewed Run
    figure : Figure
    axes : Axes
    field : String
        Read-only access to field or expression
    needs_streams : List[String], optional
        Read-only access to streams referred to by field.
    namespace : Dict, optional
        Read-only access to user-provided namespace

    Examples
    --------
    >>> model = RasteredImages("intensity", shape=(100, 200))
    >>> from bluesky_widgets.jupyter.figures import JupyterFigure
    >>> view = JupyterFigure(model.figure)
    >>> model.add_run(run)
    """

    def __init__(
        self,
        field,
        shape,
        *,
        max_runs=1,
        label_maker=None,
        needs_streams=("primary",),
        namespace=None,
        axes=None,
        clim=None,
        cmap="viridis",
        extent=None,
        x_positive="right",
        y_positive="up",
    ):
        super().__init__()

        if label_maker is None:
            # scan_id is always generated by RunEngine but not stricter required by
            # the schema, so we fail gracefully if it is missing.

            def label_maker(run, field):
                md = run.metadata["start"]
                return f"Scan ID {md.get('scan_id', '?')}   UID {md['uid'][:8]}   {field}"

        self._label_maker = label_maker

        # Stash these and expose them as read-only properties.
        self._field = field
        self._shape = shape
        self._namespace = namespace

        self._run = None

        if axes is None:
            axes = Axes()
            figure = Figure((axes,), title="")
        else:
            figure = axes.figure
        self.axes = axes
        self.figure = figure
        # If the Axes' figure is not yet set, listen for it to be set.
        if figure is None:

            def set_figure(event):
                self.figure = event.value
                # This occurs at most once, so we can now stop listening.
                self.axes.events.figure.disconnect(set_figure)

            self.axes.events.figure.connect(set_figure)
        self._clim = clim
        self._cmap = cmap
        self._extent = extent
        self._x_positive = x_positive
        self._y_positive = y_positive

        self._run_manager = RunManager(max_runs, needs_streams)
        self._run_manager.events.run_ready.connect(self._add_image)
        self.add_run = self._run_manager.add_run
        self.discard_run = self._run_manager.discard_run

    @property
    def cmap(self):
        return self._cmap

    @cmap.setter
    def cmap(self, value):
        self._cmap = value
        for artist in self.axes.artists:
            if isinstance(artist, Image):
                artist.style.update({"cmap": value})

    @property
    def clim(self):
        return self._clim

    @clim.setter
    def clim(self, value):
        self._clim = value
        for artist in self.axes.artists:
            if isinstance(artist, Image):
                artist.style.update({"clim": value})

    @property
    def extent(self):
        return self._extent

    @extent.setter
    def extent(self, value):
        self._extent = value
        for artist in self.axes.artist:
            if isinstance(artist, Image):
                artist.style.update({"extent": value})

    @property
    def x_positive(self):
        xmin, xmax = self.axes.x_limits
        if xmin > xmax:
            self._x_positive = "left"
        else:
            self._x_positive = "right"
        return self._x_positive

    @x_positive.setter
    def x_positive(self, value):
        if value not in ["right", "left"]:
            raise ValueError('x_positive must be "right" or "left"')
        self._x_positive = value
        xmin, xmax = self.axes.x_limits
        if (xmin > xmax and self._x_positive == "right") or (xmax > xmin and self._x_positive == "left"):
            self.axes.x_limits = (xmax, xmin)
        elif (xmax >= xmin and self._x_positive == "right") or (xmin >= xmax and self._x_positive == "left"):
            self.axes.x_limits = (xmin, xmax)
            self._x_positive = value

    @property
    def y_positive(self):
        ymin, ymax = self.axes.y_limits
        if ymin > ymax:
            self._y_positive = "down"
        else:
            self._y_positive = "up"
        return self._y_positive

    @y_positive.setter
    def y_positive(self, value):
        if value not in ["up", "down"]:
            raise ValueError('y_positive must be "up" or "down"')
        self._y_positive = value
        ymin, ymax = self.axes.y_limits
        if (ymin > ymax and self._y_positive == "up") or (ymax > ymin and self._y_positive == "down"):
            self.axes.y_limits = (ymax, ymin)
        elif (ymax >= ymin and self._y_positive == "up") or (ymin >= ymax and self._y_positive == "down"):
            self.axes.y_limits = (ymin, ymax)
            self._y_positive = value

    def _add_image(self, event):
        run = event.run
        func = functools.partial(self._transform, field=self.field)
        style = {"cmap": self._cmap, "clim": self._clim, "extent": self._extent}
        image = Image.from_run(func, run, label=self.field, style=style)
        self._run_manager.track_artist(image, [run])
        md = run.metadata["start"]
        self.axes.artists.append(image)
        self.axes.title = self._label_maker(run, self.field)
        self.axes.x_label = md["motors"][1]
        self.axes.y_label = md["motors"][0]
        # By default, pixels center on integer coordinates ranging from 0 to
        # columns-1 horizontally and 0 to rows-1 vertically.
        # In order to see entire pixels, we set lower limits to -0.5
        # and upper limits to columns-0.5 horizontally and rows-0.5 vertically
        # if limits aren't specifically set.
        if self.axes.x_limits is None and self._x_positive == "right":
            self.axes.x_limits = (-0.5, md["shape"][1] - 0.5)
        elif self.axes.x_limits is None and self._x_positive == "left":
            self.axes.x_limits = (md["shape"][1] - 0.5, -0.5)
        if self.axes.y_limits is None and self._y_positive == "up":
            self.axes.y_limits = (-0.5, md["shape"][0] - 0.5)
        elif self.axes.y_limits is None and self._y_positive == "down":
            self.axes.y_limits = (md["shape"][0] - 0.5, -0.5)
        # TODO Try to make the axes aspect equal unless the extent is highly non-square.
        ...

    def _transform(self, run, field):
        image_data = numpy.ones(self._shape) * numpy.nan
        result = call_or_eval({"data": field}, run, self.needs_streams, self.namespace)
        data = result["data"]
        snaking = run.metadata["start"]["snaking"]
        for index in range(len(data)):
            pos = list(numpy.unravel_index(index, self._shape))
            if snaking[1] and (pos[0] % 2):
                pos[1] = self._shape[1] - pos[1] - 1
            pos = tuple(pos)
            image_data[pos] = data[index]
        return {"array": image_data}

    @property
    def namespace(self):
        return DictView(self._namespace or {})

    @property
    def field(self):
        return self._field

    @property
    def shape(self):
        return self._shape

    # Expose some properties from the internal RunManger helper class.

    @property
    def runs(self):
        return self._run_manager.runs

    @property
    def max_runs(self):
        return self._run_manager.max_runs

    @max_runs.setter
    def max_runs(self, value):
        self._run_manager.max_runs = value

    @property
    def needs_streams(self):
        return self._run_manager._needs_streams

    @property
    def pinned(self):
        return self._run_manager._pinned
