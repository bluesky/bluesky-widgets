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

        self.model.axes.events.added.connect(self._on_axes_added)
        self.model.lines.events.added.connect(self._on_line_added)
        self.model.lines.events.removed.connect(self._on_line_removed)

    def _on_axes_added(self, event):
        axes_spec = event.item
        fig, axes, tab = _make_figure_tab()
        self._figures[tab] = fig
        self._axes[axes_spec] = axes
        # Use matplotlib's user-configurable ID so that we can look up the
        # AxesSpec from the axes if we need to.
        axes.set_gid(axes_spec.uuid)
        self._tabs.addTab(tab, "Title")  # TODO Add title to axes_spec?

    def _on_axes_removed(self, event):
        ...

    def _on_line_added(self, event):
        line = event.item
        run = line.spec.run
        x, y = line.spec.func(run)
        # Look up matplotlib.axes.Axes from AxesSpec.
        axes = self._axes[line.axes]

        # Initialize artist with currently-available data.
        (artist,) = axes.plot(x, y)
        self._lines[line] = artist
        # Use matplotlib's user-configurable ID so that we can look up the
        # LineSpec from the line artist if we need to.
        artist.set_gid(line.uuid)

        # IMPORTANT: Schedule matplotlib to redraw the canvas to include this
        # update at the next opportunity. Without this, the view may remain
        # stale indefinitely.
        axes.figure.canvas.draw_idle()

        # If this is connected to a streaming data source and is not yet
        # complete, listen for updates.
        if hasattr(run, "events") and run.metadata.stop is not None:

            def update():
                x, y = line.spec.func(run)
                artist.set_data(x, y)
                axes.figure.canvas.draw_idle()

            run.events.new_data.connect(update)
            run.events.completed.connect(lambda: run.events.new_data.disconnect(update))

    def _on_line_removed(self, event):
        line = event.item
        artist = self._lines.pop(line)
        artist.remove()
        axes = self._axes[line.axes]
        axes.figure.canvas.draw_idle()


class _QtViewerTabs(QTabWidget):
    ...


def _make_figure_tab():
    matplotlib.use("Qt5Agg")  # must set before importing matplotlib.pyplot
    import matplotlib.pyplot as plt  # noqa

    tab = QWidget()
    fig, axes = plt.subplots()
    canvas = FigureCanvas(fig)
    canvas.setMinimumWidth(640)
    canvas.setParent(tab)
    toolbar = NavigationToolbar(canvas, tab)

    layout = QVBoxLayout()
    layout.addWidget(canvas)
    layout.addWidget(toolbar)
    tab.setLayout(layout)
    return fig, axes, tab
