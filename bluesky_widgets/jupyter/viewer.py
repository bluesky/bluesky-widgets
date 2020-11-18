import collections.abc
import gc
import logging

from ipywidgets import widgets
import matplotlib


class JupyterViewer(widgets.VBox):
    """
    A Jupyter (ipywidgets) view for a Viewer model.
    """

    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        # Map Figure UUID to widget with Figure
        self._figures = {}
        # Map Axes UUID to matplotlib.axes.Axes
        self._axes = {}
        # Map ArtistSpec UUID to matplotlib artist
        self._artists = {}
        self._tabs = _JupyterViewerTabs(model.figures)
        self.children = [self._tabs]

        self.model.figures.events.added.connect(self._on_figure_added)
        self.model.figures.events.removed.connect(self._on_figure_removed)
        self.model.lines.events.added.connect(self._on_line_added)
        self.model.lines.events.removed.connect(self._on_line_removed)

    def _on_figure_added(self, event):
        figure_spec = event.item
        tab = _JupyterFigureTab(figure_spec, self._tabs)
        self._figures[figure_spec.uuid] = tab
        for axes_spec, axes in zip(figure_spec.axes_specs, tab.axes_list):
            axes.set_xlabel(axes_spec.x_label)
            axes.set_ylabel(axes_spec.y_label)

            self._axes[axes_spec.uuid] = axes
            # Use matplotlib's user-configurable ID so that we can look up the
            # AxesSpec from the axes if we need to.
            axes.set_gid(axes_spec.uuid)

        tab.figure.tight_layout()
        self._tabs.children = (*self._tabs.children, tab)
        index = len(self._tabs.children) - 1
        self._tabs.set_title(index, figure_spec.title)
        # Workaround: If the tabs are cleared and then children are added
        # again, no tab is selected.
        if index == 0:
            self._tabs.selected_index = 0

    def _on_figure_removed(self, event):
        # A Search has been removed from the SearchList model.
        # Close the associated tab and clean up the associated state.
        figure_spec = event.item
        widget = self._figures[figure_spec.uuid]
        children = list(self._tabs.children)
        children.remove(widget)
        self._tabs.children = tuple(children)
        widget.figure.canvas.close()
        del self._figures[figure_spec.uuid]
        gc.collect()

    def _on_line_added(self, event):
        line_spec = event.item
        run = line_spec.run
        x, y = line_spec.func(run)
        # Look up matplotlib.axes.Axes from AxesSpec.
        axes = self._axes[line_spec.axes_spec.uuid]

        # Initialize artist with currently-available data.
        (artist,) = axes.plot(x, y, **line_spec.artist_kwargs)
        self._artists[line_spec.uuid] = artist
        # Use matplotlib's user-configurable ID so that we can look up the
        # LineSpec from the line artist if we need to.
        artist.set_gid(line_spec.uuid)

        # Listen for changes to artist_kwargs.
        line_spec.events.artist_kwargs.connect(self._on_artist_kwargs_changed)

        # This legend can only be turned on after there is at least one artist.
        axes.legend(loc="best")

        # IMPORTANT: Schedule matplotlib to redraw the canvas to include this
        # update at the next opportunity. Without this, the view may remain
        # stale indefinitely.
        axes.figure.canvas.draw_idle()

        # If this is connected to a streaming data source and is not yet
        # complete, listen for updates.
        if hasattr(run, "events") and (run.metadata["stop"] is None):

            def update(event):
                x, y = line_spec.func(run)
                artist.set_data(x, y)
                axes.relim()  # Recompute data limits.
                axes.autoscale_view()  # Rescale the view using those new limits.
                axes.figure.canvas.draw_idle()

            run.events.new_data.connect(update)
            run.events.completed.connect(
                lambda event: run.events.new_data.disconnect(update)
            )

    def _on_artist_kwargs_changed(self, event):
        artist_spec = event.source
        artist = self._artists[artist_spec.uuid]
        artist.set(**event.value)
        axes = self._axes[artist_spec.axes_spec.uuid]
        axes.legend(loc="best")  # Update the legend.
        axes.figure.canvas.draw_idle()

    def _on_line_removed(self, event):
        line_spec = event.item
        line_artist = self._artists.pop(line_spec.uuid)
        line_artist.remove()
        axes = self._axes[line_spec.axes_spec.uuid]
        axes.legend(loc="best")  # Update the legend.
        axes.figure.canvas.draw_idle()


class _JupyterViewerTabs(widgets.Tab):
    """
    A container of tabs, wrapping a Viewer model
    """

    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model

    def close_tab(self, model):
        # When closing is initiated from the view, remove the associated
        # model.
        self.model.remove(model)


class _JupyterFigureTab(widgets.HBox):
    """
    A Jupyter view for a FigureSpec model. This always contains one Figure.
    """

    def __init__(self, model, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.parent = parent
        self.figure, self.axes_list = _make_figure(model)
        self.button = widgets.Button(description="Close")
        self.button.on_click(lambda _: self.parent.close_tab(self.model))
        self.children = (self.figure.canvas, self.button)


def _make_figure(figure_spec):
    "Create a Figure in a QWidget."
    matplotlib.use(
        "module://ipympl.backend_nbagg"
    )  # must set before importing matplotlib.pyplot
    import matplotlib.pyplot as plt  # noqa

    # By default, with interactive mode on, each fig.show() will be called
    # automatically, and we'll get duplicates littering the output area. We
    # only want to see the figures where they are placed explicitly in widgets.
    plt.ioff()

    # TODO Let FigureSpec give different options to subplots here,
    # but verify that number of axes created matches the number of axes_specs.
    figure, axes = plt.subplots(len(figure_spec.axes_specs))
    # Handle return type instability in plt.subplots.
    if not isinstance(axes, collections.abc.Iterable):
        axes = [axes]
    return figure, axes


def _quiet_mpl_noisy_logger():
    "Do not filter or silence it, but avoid defaulting to the logger of last resort."
    logger = logging.getLogger("matplotlib.legend")
    logger.addHandler(logging.NullHandler())


_quiet_mpl_noisy_logger()
