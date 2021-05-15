import abc

from ..plot_specs import FigureList
from ..utils import run_is_live_and_not_completed
from ...utils.list import EventedList


class AutoPlotter(abc.ABC):
    """
    Generate best-effort figures based on a heuristic.

    Subclasses must define the method ``handle_new_stream``.

    Parameters
    ----------
    plot_suggestors : List[PlotSuggestors]
    max_runs : Integer, optional
        Default, ``None``, defers to the default of the ``plot_builder``.
    """

    def __init__(self):
        self.figures = FigureList()
        self.figures.events.removed.connect(self._on_figure_removed)
        self.plot_builders = EventedList()

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
            self.handle_new_stream(run, stream_name, **kwargs)
        if run_is_live_and_not_completed(run):
            # Listen for additional streams.

            def pass_to_handle_new_stream(event):
                self.handle_new_stream(run, event.name, **kwargs)

            run.events.new_stream.connect(pass_to_handle_new_stream)
            # When run is complete, stop listening.
            run.events.completed.connect(lambda event: run.events.new_stream.disconnect(pass_to_handle_new_stream))

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
        for plot_builder in self.plot_builders:
            plot_builder.discard_run(run)

    @abc.abstractmethod
    def handle_new_stream(self, run, stream_name, **kwargs):
        "Build a plot, or add to an existing plot, or do nothing."

    def handle_figure_removed(self, figure):
        for plot_builder in list(self.plot_builders):
            if hasattr(plot_builder, "figure"):
                if figure is plot_builder.figure:
                    self.plot_builders.remove(plot_builder)
            elif hasattr(plot_builder, "figures"):
                for figure in self.figures:
                    if figure is plot_builder.figure:
                        self.plot_builders.remove(plot_builder)
            else:
                ValueError("A plot builder is expected to have an attribute `figure` or `figures`")

    def _on_figure_removed(self, event):
        self.handle_figure_removed(event.item)
