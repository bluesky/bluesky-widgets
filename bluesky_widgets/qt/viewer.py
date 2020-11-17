import collections.abc

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


class QtViewer(QWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        # Map widget in tab to matplotlib figure.
        self._figures = {}
        # Map Axes to matplotlib.axes.Axes
        self._axes = {}
        # Map Line to matplotlib Line artist
        self._lines = {}
        layout = QVBoxLayout()
        self._tabs = _QtViewerTabs()
        layout.addWidget(self._tabs)
        self.setLayout(layout)

        self.model.figures.events.added.connect(self._on_figure_added)
        self.model.lines.events.added.connect(self._on_line_added)
        self.model.lines.events.removed.connect(self._on_line_removed)

    def _on_figure_added(self, event):
        figure_spec = event.item
        fig, axes_list, tab = _make_figure_tab(len(figure_spec.axes_specs))
        self._figures[tab] = fig
        for axes_spec, axes in zip(figure_spec.axes_specs, axes_list):
            axes.set_xlabel(axes_spec.x_label)
            axes.set_ylabel(axes_spec.y_label)

            self._axes[axes_spec] = axes
            # Use matplotlib's user-configurable ID so that we can look up the
            # AxesSpec from the axes if we need to.
            axes.set_gid(axes_spec.uuid)

        fig.tight_layout()
        self._tabs.addTab(tab, figure_spec.title)

    def _on_figure_removed(self, event):
        ...

    def _on_line_added(self, event):
        line_spec = event.item
        run = line_spec.run
        x, y = line_spec.func(run)
        # Look up matplotlib.axes.Axes from AxesSpec.
        axes = self._axes[line_spec.axes_spec]

        # Initialize artist with currently-available data.
        (artist,) = axes.plot(x, y, *line_spec.args, **line_spec.kwargs)
        self._lines[line_spec] = artist
        # Use matplotlib's user-configurable ID so that we can look up the
        # LineSpec from the line artist if we need to.
        artist.set_gid(line_spec.uuid)

        # This legend can only be turned on after there is at least one artist.
        axes.legend(loc="best")

        # IMPORTANT: Schedule matplotlib to redraw the canvas to include this
        # update at the next opportunity. Without this, the view may remain
        # stale indefinitely.
        axes.figure.canvas.draw_idle()

        # If this is connected to a streaming data source and is not yet
        # complete, listen for updates.
        if hasattr(run, "events") and run.metadata.stop is not None:

            def update():
                x, y = line_spec.func(run)
                artist.set_data(x, y)
                axes.figure.canvas.draw_idle()

            run.events.new_data.connect(update)
            run.events.completed.connect(lambda: run.events.new_data.disconnect(update))

    def _on_line_removed(self, event):
        line_spec = event.item
        line_artist = self._lines.pop(line_spec)
        line_artist.remove()
        axes = self._axes[line_spec.axes]
        axes.figure.canvas.draw_idle()


class _QtViewerTabs(QTabWidget):
    ...


def _make_figure_tab(*args, **kwargs):
    "Create a Figure in a QWidget. Pass args, kwargs to pyplot.subplots()."
    matplotlib.use("Qt5Agg")  # must set before importing matplotlib.pyplot
    import matplotlib.pyplot as plt  # noqa

    tab = QWidget()
    fig, axes = plt.subplots(*args, **kwargs)
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
