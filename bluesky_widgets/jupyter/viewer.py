import collections.abc
import gc
import logging

from ipywidgets import widgets
import matplotlib

from ..models.plot_specs import FigureSpec, FigureSpecList, AxesSpec, LineSpec


class JupyterFigures(widgets.Tab):
    """
    A Jupyter (ipywidgets) view for a FigureSpecList model.
    """
    def __init__(self, model: FigureSpecList, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        # Map Figure UUID to widget with JupyterFigureTab
        self._figures = {}

        for figure_spec in model:
            self._add_figure(figure_spec)
        self.model.events.added.connect(self._on_figure_added)
        self.model.events.removed.connect(self._on_figure_removed)

    def _on_figure_added(self, event):
        figure_spec = event.item

    def _add_figure(self, figure_spec):
        tab = _JupyterFigureTab(figure_spec, parent=self)
        self._figures[figure_spec.uuid] = tab
        self.children = (*self.children, tab)
        index = len(self.children) - 1
        self.set_title(index, figure_spec.title)
        # Workaround: If the tabs are cleared and then children are added
        # again, no tab is selected.
        if index == 0:
            self.selected_index = 0

    def _on_figure_removed(self, event):
        # A Search has been removed from the SearchList model.
        # Close the associated tab and clean up the associated state.
        figure_spec = event.item
        widget = self._figures[figure_spec.uuid]
        children = list(self.children)
        children.remove(widget)
        self.children = tuple(children)
        widget.figure.canvas.close()
        del self._figures[figure_spec.uuid]
        gc.collect()

    def close_tab(self, model):
        # When closing is initiated from the view, remove the associated
        # model.
        self.model.remove(model)


class JupyterFigure(widgets.HBox):
    """
    A Jupyter view for a FigureSpec model. This always contains one Figure.
    """

    def __init__(self, model: FigureSpec):
        super().__init__()
        self.model = model
        self.figure, self.axes_list = _make_figure(model)
        self._axes = {}
        for axes_spec, axes in zip(model.axes_specs, self.axes_list):
            self._axes[axes_spec.uuid] = Axes(axes_spec, axes)
        self.children = (self.figure.canvas,)

        # The FigureSpec model does not currently allow axes to be added or
        # removed, so we do not need to handle changes in model.axes_specs.


class _JupyterFigureTab(widgets.HBox):
    """
    A tab in a widgets.Tab container that contains a JupyterFigure.

    This is aware of its parent in order to support tab-closing.
    """
    def __init__(self, model: FigureSpec, parent):
        super().__init__()
        self.parent = parent
        self.button = widgets.Button(description="Close")
        self.button.on_click(lambda _: self.parent.close_tab(self.model))
        self.jupyter_figure = JupyterFigure(model)
        self.children = (self.jupyter_figure, self.button)


class Axes:
    "Respond to changes in AxesSpec by maniupatling matplotlib.axes.Axes."
    def __init__(self, model: AxesSpec, axes):
        self.model = model
        self.axes = axes

        axes.set_xlabel(model.x_label)
        axes.set_ylabel(model.y_label)

        # Use matplotlib's user-configurable ID so that we can look up the
        # AxesSpec from the axes if we need to.
        axes.set_gid(model.uuid)

        # Keep a reference to all types of artist here.
        self._artists = {}
        # And keep type-specific references in type-specific caches.
        self._lines = {}

        self.type_map = {
            LineSpec: self._lines,
        }

        for line_spec in model.lines:
            self._add_line(line_spec)
        model.lines.events.added.connect(self._on_line_added)
        model.lines.events.removed.connect(self._on_artist_removed)

    def _on_line_added(self, event):
        line_spec = event.item
        self._add_line(self, line_spec)

    def _add_line(self, line_spec):
        run = line_spec.run
        x, y = line_spec.func(run)

        # Initialize artist with currently-available data.
        (artist,) = self.axes.plot(x, y, **line_spec.artist_kwargs)
        self._lines[line_spec.uuid] = artist

        # If this is connected to a streaming data source and is not yet
        # complete, listen for updates.
        if hasattr(run, "events") and (run.metadata["stop"] is None):

            def update(event):
                x, y = line_spec.func(run)
                artist.set_data(x, y)
                self.axes.relim()  # Recompute data limits.
                self.axes.autoscale_view()  # Rescale the view using those new limits.
                self.axes.figure.canvas.draw_idle()

            run.events.new_data.connect(update)
            run.events.completed.connect(
                lambda event: run.events.new_data.disconnect(update)
            )

        self._on_artist_added(line_spec, artist)

    def _add_artist(self, artist_spec, artist):
        """
        This is called by methods line _add_line to perform generic setup.
        """
        self._artists[artist_spec.uuid] = artist
        # Use matplotlib's user-configurable ID so that we can look up the
        # ArtistSpec from the artist artist if we need to.
        artist.set_gid(artist_spec.uuid)

        # Listen for changes to artist_kwargs.
        artist_spec.events.artist_kwargs.connect(self._on_artist_kwargs_changed)
        self._redraw()

    def _on_artist_kwargs_changed(self, event):
        artist_spec = event.source
        artist = self._artists[artist_spec.uuid]
        artist.set(**event.value)
        self._redraw()

    def _on_artist_removed(self, event):
        artist_spec = event.item
        # Remove the artist from our caches.
        artist = self._artists.pop(artist_spec.uuid)
        self.type_map[artist_spec].pop(artist_spec.uuid)
        # Remove it from the canvas.
        artist.remove()
        self._redraw()

    def _redraw(self):
        self.axes.legend(loc="best")  # Update the legend.
        # Schedule matplotlib to redraw the canvas to at the next opportunity.
        self.axes.figure.canvas.draw_idle()


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
    figure.tight_layout()
    # Handle return type instability in plt.subplots.
    if not isinstance(axes, collections.abc.Iterable):
        axes = [axes]
    return figure, axes


def _quiet_mpl_noisy_logger():
    "Do not filter or silence it, but avoid defaulting to the logger of last resort."
    logger = logging.getLogger("matplotlib.legend")
    logger.addHandler(logging.NullHandler())


_quiet_mpl_noisy_logger()
