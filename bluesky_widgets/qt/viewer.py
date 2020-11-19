import collections.abc
import gc
import logging

from qtpy.QtWidgets import (
    QTabWidget,
    QWidget,
    QVBoxLayout,
)
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
import matplotlib

from .teleporter import threadsafe_connect, initialize_qt_teleporter


class QtViewer(QWidget):
    """
    A Qt view for a Viewer model.
    """

    def __init__(self, model, *args, **kwargs):
        initialize_qt_teleporter()
        super().__init__(*args, **kwargs)
        self.model = model
        # Map Figure UUID to (matplotlib.figure.Figure, widget).
        self._figures = {}
        # Map Axes UUID to matplotlib.axes.Axes
        self._axes = {}
        # Map ArtistSpec UUID to matplotlib artist
        self._artists = {}
        layout = QVBoxLayout()
        self._tabs = _QtViewerTabs(model.figures, parent=self)
        layout.addWidget(self._tabs)
        self.setLayout(layout)

        threadsafe_connect(self.model.figures.events.added, self._on_figure_added)
        threadsafe_connect(self.model.figures.events.removed, self._on_figure_removed)
        threadsafe_connect(self.model.lines.events.added, self._on_line_added)
        threadsafe_connect(self.model.lines.events.removed, self._on_line_removed)

    def _on_figure_added(self, event):
        figure_spec = event.item
        fig, axes_list, tab = _make_figure_tab(figure_spec)
        tab.setParent(self._tabs)
        self._figures[figure_spec.uuid] = (fig, tab)
        for axes_spec, axes in zip(figure_spec.axes_specs, axes_list):
            axes.set_xlabel(axes_spec.x_label)
            axes.set_ylabel(axes_spec.y_label)

            self._axes[axes_spec.uuid] = axes
            # Use matplotlib's user-configurable ID so that we can look up the
            # AxesSpec from the axes if we need to.
            axes.set_gid(axes_spec.uuid)

        fig.tight_layout()
        self._tabs.addTab(tab, figure_spec.title)

    def _on_figure_removed(self, event):
        # A Search has been removed from the SearchList model.
        # Close the associated tab and clean up the associated state.
        figure_spec = event.item
        fig, widget = self._figures[figure_spec.uuid]
        index = self._tabs.indexOf(widget)
        self._tabs.removeTab(index)
        fig.canvas.close()
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


class _QtViewerTabs(QTabWidget):
    """
    A container of tabs, wrapping a Viewer model
    """

    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)

    def close_tab(self, index):
        # When closing is initiated from the view, remove the associated
        # model.
        widget = self.widget(index)
        self.model.remove(widget.model)


class _QtFigureTab(QWidget):
    """
    A Qt view for a FigureSpec model. This always contains one Figure.
    """

    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model


def _make_figure_tab(figure_spec):
    "Create a Figure in a QWidget."
    matplotlib.use("Qt5Agg")  # must set before importing matplotlib.pyplot
    import matplotlib.pyplot as plt  # noqa

    tab = _QtFigureTab(figure_spec)
    # TODO Let FigureSpec give different options to subplots here,
    # but verify that number of axes created matches the number of axes_specs.
    fig, axes = plt.subplots(len(figure_spec.axes_specs))
    # Handl return type instability in plt.subplots.
    if not isinstance(axes, collections.abc.Iterable):
        axes = [axes]
    canvas = FigureCanvas(fig)
    canvas.setMinimumWidth(640)
    canvas.setParent(tab)
    toolbar = NavigationToolbar(canvas, tab)

    layout = QVBoxLayout()
    layout.addWidget(canvas)
    layout.addWidget(toolbar)
    tab.setLayout(layout)
    return fig, axes, tab


def _quiet_mpl_noisy_logger():
    "Do not filter or silence it, but avoid defaulting to the logger of last resort."
    logger = logging.getLogger("matplotlib.legend")
    logger.addHandler(logging.NullHandler())


_quiet_mpl_noisy_logger()
