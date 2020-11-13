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
        # Map AxesSpec to matplotlib.axes.Axes
        self._axes = {}
        # Axes
        layout = QVBoxLayout()
        self._tabs = _QtViewerTabs()
        layout.addWidget(self._tabs)
        self.setLayout(layout)

        self.model.axes.events.added.connect(self._on_axes_added)
        self.model.lines.events.added.connect(self._on_lines_added)

    def _on_axes_added(self, event):
        axes_spec = event.item
        fig, axes, tab = _make_figure_tab()
        self._figures[tab] = fig
        self._axes[axes_spec] = axes
        self._tabs.addTab(tab, "Title")  # TODO Add title to axes_spec?

    def _on_lines_added(self, event):
        line = event.item
        run = line.run
        x, y = line.func(run)
        # Look up matplotlib.axes.Axes from AxesSpec.
        axes = self._axes[line.axes]

        # Initialize artist with currently-available data.
        (artist,) = axes.plot(x, y)

        # If this is connected to a streaming data source and is not yet
        # complete, listen for updates.
        if hasattr(run, "events") and run.metadata.stop is not None:

            def update():
                x, y = line.func(run)
                artist.set_data(x, y)

            run.events.new_data.connect(update)
            run.events.completed.connect(lambda: run.events.new_data.disconnect(update))


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
