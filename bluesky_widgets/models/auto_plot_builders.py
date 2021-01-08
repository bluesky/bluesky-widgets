from collections import defaultdict
import itertools

from .utils import run_is_live_and_not_completed
from .plot_specs import AxesSpec, FigureSpec, FigureSpecList
from .plot_builders import Lines
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

        # Map suggestion to a plot_builder instance configured with it.
        self._suggestion_to_plot_builder = {}
        # Map FigureSpec UUID to suggestion.
        self._figure_to_suggestion = {}
        # Track inactive plot_builders/figures which are no longer being updated
        # with new Runs. Structure is a dict-of-dicts like:
        # {suggestion: {figure_uuid: plot_builder, ...}, ...}
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
            suggestion = self._figure_to_suggestion[figure.uuid]
            plot_builder = self._suggestion_to_plot_builder[suggestion]
            plot_builders.append(plot_builder)
        return tuple(plot_builders)

    def new_plot_builders_for_suggestions(self, suggestions):
        """
        Make new plot_builder(s) for suggestion(s).

        If there is an existing one the plot_builder and figure will remain but
        will no longer be updated with new Runs. Those will go to a new
        plot_builder and figure, created here.
        """
        # Demote the existing plot_builder for each suggestion (if any).
        for suggestion in suggestions:
            old_plot_builder = self._suggestion_to_plot_builder.pop(suggestion, None)
            if old_plot_builder is not None:
                self._inactive_plot_builders[suggestion][
                    old_plot_builder.figure.uuid
                ] = old_plot_builder

        plot_builders = []  # the return value
        # Group the suggestion by their plot_builder_class, and then
        # handle their internal 'group' designation to do things like
        # place axes on the same figure.
        # TODO In the future we may want to allow shared figures
        # across plot_builder_class types. This is provisional.
        grouped_by_class = {
            k: list(v)
            for k, v in itertools.groupby(
                suggestions, key=lambda suggestion: suggestion[0]
            )
        }
        line_suggestions = list(grouped_by_class.pop(Lines, []))
        # A Line suggestion has a group with a figure title.
        for figure_title, group_of_line_suggestions in itertools.groupby(
            line_suggestions, key=lambda suggestion: suggestion[2]
        ):
            axes_list = []
            for suggestion in group_of_line_suggestions:
                axes = AxesSpec()
                axes_list.append(axes)
                _, parameters, _ = suggestion
                plot_builder = Lines(**dict(parameters), axes=axes)
                plot_builders.append(plot_builder)
                self._suggestion_to_plot_builder[suggestion] = plot_builder
            figure = FigureSpec(axes_list, title=figure_title)
            self._figure_to_suggestion[figure.uuid] = suggestion
            self.figures.append(figure)
        # Handle all other types of suggestion generically.
        for _, group_of_suggestions in grouped_by_class.items():
            for suggestion in group_of_suggestions:
                plot_builder_class, parameters, _ = suggestion
                plot_builder = plot_builder_class(**dict(parameters))
                plot_builders.append(plot_builder)
                self._suggestion_to_plot_builder[suggestion] = plot_builder
                self._figure_to_suggestion[plot_builder.figure.uuid] = suggestion
                self.figures.append(plot_builder.figure)
        return plot_builders

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
        for plot_builder in self._suggestion_to_plot_builder.values():
            plot_builder.discard_run(run)

    def _handle_stream(self, run, stream_name, **kwargs):
        "This examines a stream and adds this run to plot_builders."
        suggestions = []
        for plot_suggestor in self.plot_suggestors:
            for raw_suggestion in plot_suggestor.suggest(run, stream_name):
                # If the parameters are given as a dict, convert them to a
                # tuple of (key, value) pairs so that they are hashable.
                # TODO Use some other scheme for this.
                plot_builder_class, parameters, group = raw_suggestion
                suggestion = (
                    plot_builder_class,
                    tuple(dict(parameters).items()),
                    group,
                )
                # If we already have a plot builder instance for this
                # suggestion, use it. If not, add the suggestion to a list to
                # be handled in a batch at the end.
                try:
                    plot_builder = self._suggestion_to_plot_builder[suggestion]
                except KeyError:
                    suggestions.append(suggestion)
                else:
                    plot_builder.add_run(run, **kwargs)
        # Create plot builders for all the suggestions that we don't already
        # have plot builders for.
        plot_builders = self.new_plot_builders_for_suggestions(suggestions)
        for plot_builder in plot_builders:
            plot_builder.add_run(run, **kwargs)

    def _on_figure_removed(self, event):
        """
        A figure was removed from self.figures.

        Remove the relevant plot_builder.
        """
        figure = event.item
        try:
            suggestion = self._figure_to_suggestion.pop(figure.uuid)
        except KeyError:
            # This figure belongs to an inactive plot_builder.
            del self._inactive_plot_builders[suggestion][figure.uuid]

        else:
            self._suggestion_to_plot_builder.pop(suggestion)


best_effort_viz = AutoPlotter([GenericPlotSuggestor])
