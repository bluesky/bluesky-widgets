from collections import defaultdict
from functools import partial

from ..utils.dict_view import DictView
from .utils import run_is_live_and_not_completed
from .plot_specs import FigureSpecList
from .plot_builders import Lines, Images
from .heuristics import infer_images, infer_lines_to_plot


class AutoPlotter:
    """
    Generate best-effort figures based on a heuristic.

    Parameters
    ----------
    plot_builder : object
        Plot-builder model, such as Lines or Images. Expected to implement:
        * add_run(run, **kwargs)  # kwargs are optional, builder-dependent
        * discard_run(run)
        * figure -> FigureSpec

    heuristic : callable
        Callable that suggests what to plot

        Expected signature::

            f(run: BlueskyRun, steam_name: String) -> List[Dict]

        where Dict is kwargs accepted by ``plot_builder.__init__``.
    max_runs : Integer, optional
        Default, ``None``, defers to the default of the ``plot_builder``.
    extra_kwargs : Dict, optional
        Passed to ``plot_buidler.__init__``.

    Examples
    --------

    Automaticaly plot some useful lines.

    >>> from bluesky_widgets.models.plot_builders import Lines
    >>> from bluesky_widgets.models.heuristics import infer_lines_to_plot
    >>> model = AutoPlotter(Lines, infer_lines_to_plot)

    Automatically plot all the images.

    >>> from bluesky_widgets.models.plot_builders import Images
    >>> from bluesky_widgets.models.heuristics import infer_images
    >>> model = AutoPlotter(Images, infer_images)

    See Also
    --------
    AutoLines
    AutoImages
    """

    def __init__(self, plot_builder, heuristic, **extra_kwargs):
        self._plot_builder = plot_builder
        self._heuristic = heuristic
        self._extra_kwargs = extra_kwargs or {}

        self.figures = FigureSpecList()

        # Map key like to plot_builder plot_builder so configured.
        self._key_to_plot_builder = {}
        # Map FigureSpec UUID to key like ((x, y), stream_name)
        self._figure_to_key = {}
        # Track inactive plot_builders/figures which are no longer being updated
        # with new Runs. Structure is a dict-of-dicts like:
        # {key: {figure_uuid: plot_builder, ...}, ...}
        self._inactive_plot_builders = defaultdict(dict)
        self.figures.events.removed.connect(self._on_figure_removed)

    @property
    def plot_builder(self):
        return self._plot_builder

    @property
    def heuristic(self):
        return self._heuristic

    @property
    def extra_kwargs(self):
        return DictView(self._extra_kwargs)

    @property
    def plot_builders(self):
        "Tuple of plot_builders corresponding to figures."
        plot_builders = []
        for figure in self.figures:
            key = self._figure_to_key[figure.uuid]
            plot_builder = self._key_to_plot_builder[key]
            plot_builders.append(plot_builder)
        return tuple(plot_builders)

    def new_plot_builder_for_key(self, key):
        """
        Make a new plot_builder for a key.

        If there is an existing one the plot_builder and figure will remain but
        will no longer be updated with new Runs. Those will go to a new
        plot_builder and figure, created here.
        """
        old_plot_builder = self._key_to_plot_builder.pop(key, None)
        if old_plot_builder is not None:
            self._inactive_plot_builders[key][
                old_plot_builder.figure.uuid
            ] = old_plot_builder
        plot_builder = self._plot_builder(**dict(key, **self._extra_kwargs))
        self._key_to_plot_builder[key] = plot_builder
        self._figure_to_key[plot_builder.figure.uuid] = key
        self.figures.append(plot_builder.figure)
        return plot_builder

    def add_run(self, run, **kwargs):
        """
        Add a Run.

        Parameters
        ----------
        run : BlueskyRun
        **kwargs
            Passed through to plot_builder
        """
        for stream_name in run:
            self._handle_stream(run, stream_name, **kwargs)
        if run_is_live_and_not_completed(run):
            # Listen for additional streams.
            run.events.new_stream.connect(
                lambda event: self._handle_stream(run, event.name, **kwargs)
            )

    def discard_run(self, run):
        """
        Discard a Run.

        If the Run is not present, this will return silently. Also,
        note that this only affect "active" plots that are currently
        receive new runs. Inactive ones will be left as they are.

        Parameters
        ----------
        run : BlueskyRun
        """
        for plot_builder in self._key_to_plot_builder.values():
            plot_builder.discard_run(run)

    def _handle_stream(self, run, stream_name, **kwargs):
        "This examines a stream and adds this run to plot_builders."
        for suggestion in self._heuristic(run, stream_name):
            # Make a hashable `key` out of the dict `suggestions`.
            key = tuple(suggestion.items())
            try:
                plot_builder = self._key_to_plot_builder[key]
            except KeyError:
                plot_builder = self.new_plot_builder_for_key(key)
            plot_builder.add_run(run, **kwargs)

    def _on_figure_removed(self, event):
        """
        A figure was removed from self.figures.

        Remove the relevant plot_builder.
        """
        figure = event.item
        try:
            key = self._figure_to_key.pop(figure.uuid)
        except KeyError:
            # This figure belongs to an inactive plot_builder.
            del self._inactive_plot_builders[key][figure.uuid]

        else:
            self._key_to_plot_builder.pop(key)


# For ease of use, preconfigure some AutoPlotters for various plot types with
# general-purpose heuristics.

AutoLines = partial(AutoPlotter, plot_builder=Lines, heuristic=infer_lines_to_plot)
AutoImages = partial(AutoPlotter, plot_builder=Images, heuristic=infer_images)
