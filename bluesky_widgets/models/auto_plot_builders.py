from collections import defaultdict

from .utils import run_is_live_and_not_completed
from .plot_specs import FigureSpecList
from ..utils.list import EventedList
from .heuristics import GenericPlotSuggestor


class PlotSuggestorList(EventedList):
    ...


class AutoPlotter:
    """
    Generate best-effort figures based on a heuristic.

    Parameters
    ----------
    plot_suggestors : List[PlotSuggestors]
    max_runs : Integer, optional
        Default, ``None``, defers to the default of the ``plot_builder``.
    """

    def __init__(self, plot_suggestors):
        self._plot_suggestors = PlotSuggestorList(plot_suggestors)

        self.figures = FigureSpecList()

        # Map key (which contains a plot_builder configuration) to a
        # plot_builder instance configured with it.
        self._key_to_plot_builder = {}
        # Map FigureSpec UUID to key.
        self._figure_to_key = {}
        # Track inactive plot_builders/figures which are no longer being updated
        # with new Runs. Structure is a dict-of-dicts like:
        # {key: {figure_uuid: plot_builder, ...}, ...}
        self._inactive_plot_builders = defaultdict(dict)
        self.figures.events.removed.connect(self._on_figure_removed)

    @property
    def plot_suggestors(self):
        return self._plot_suggestors

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
        plot_builder_class, parameters, group = key
        # TODO brains about sharing axes based on the group
        plot_builder = plot_builder_class(**dict(parameters))
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
        for plot_suggestor in self.plot_suggestors:
            for suggestion in plot_suggestor.suggest(run, stream_name):
                # Make a hashable `key` out of the dict `suggestions`.
                # TODO Use some other tokenziation scheme here.
                plot_builder_class, parameters, group = suggestion
                breakpoint()
                key = (plot_builder_class, tuple(parameters.items()), group)
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


best_effort_viz = AutoPlotter([GenericPlotSuggestor])
