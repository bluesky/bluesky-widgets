import collections.abc
import gc

from qtpy.QtWidgets import (
    QTabWidget,
    QWidget,
    QVBoxLayout,
)
from qtpy.QtCore import Signal, QObject
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
import matplotlib

from ..models.plot_specs import FigureSpec, FigureSpecList
from .._matplotlib_axes import MatplotlibAxes
from ..utils.event import Event
from ..utils.dict_view import DictView


class ThreadsafeMatplotlibAxes(QObject, MatplotlibAxes):
    """
    This overrides the a connect method in MatplotlibAxes to bounce callbacks
    through Qt Signals and Slots so that callbacks run form background threads
    do not run amok.
    """

    __callback_event = Signal(object, Event)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def handle_callback(callback, event):
            callback(event)

        self.__callback_event.connect(handle_callback)

    def connect(self, emitter, callback):
        emitter.connect(lambda event: self.__callback_event.emit(callback, event))


class QtFigures(QTabWidget):
    """
    A Jupyter (ipywidgets) view for a FigureSpecList model.
    """

    __callback_event = Signal(object, Event)

    def __init__(self, model: FigureSpecList, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._on_close_tab_requested)

        self.model = model
        # Map Figure UUID to widget with QtFigureTab
        self._figures = {}

        for figure_spec in model:
            self._add_figure(figure_spec)
        self._threadsafe_connect(model.events.added, self._on_figure_added)
        self._threadsafe_connect(model.events.removed, self._on_figure_removed)

        # This setup for self._threadsafe_connect.

        def handle_callback(callback, event):
            callback(event)

        self.__callback_event.connect(handle_callback)

    @property
    def figures(self):
        "Read-only access to the mapping FigureSpec UUID -> QtFigure"
        return DictView(self._figures)

    def _threadsafe_connect(self, emitter, callback):
        """
        A threadsafe method for connecting to models.

        For example, instead of

        >>> model.events.addded.connect(callback)

        use

        >>> self._threadsafe_connect(model.events.added, callback)
        """
        emitter.connect(lambda event: self.__callback_event.emit(callback, event))

    def _on_close_tab_requested(self, index):
        # When closing is initiated from the view, remove the associated
        # model.
        widget = self.widget(index)
        self.model.remove(widget.model)

    def _on_figure_added(self, event):
        figure_spec = event.item
        self._add_figure(figure_spec)

    def _add_figure(self, figure_spec):
        "Add a new tab with a matplotlib Figure."
        tab = QtFigure(figure_spec, parent=self)
        self.addTab(tab, figure_spec.title)
        self._figures[figure_spec.uuid] = tab
        # TODO On figure_spec.events.title, update tab title.

    def _on_figure_removed(self, event):
        "Remove the associated tab and close its canvas."
        figure_spec = event.item
        widget = self._figures[figure_spec.uuid]
        index = self.indexOf(widget)
        self.removeTab(index)
        widget.figure.canvas.close()
        del widget
        del self._figures[figure_spec.uuid]
        # Ensure that the canvas widget is cleaned up.
        gc.collect()


class QtFigure(QWidget):
    """
    A Qt view for a FigureSpec model. This always contains one Figure.
    """

    def __init__(self, model: FigureSpec, parent=None):
        super().__init__(parent)
        self.model = model
        self.figure, self.axes_list = _make_figure(model)
        self.figure.suptitle(model.title)
        self._axes = {}
        for axes_spec, axes in zip(model.axes, self.axes_list):
            self._axes[axes_spec.uuid] = ThreadsafeMatplotlibAxes(
                model=axes_spec, axes=axes
            )
        canvas = FigureCanvas(self.figure)
        canvas.setMinimumWidth(640)
        canvas.setParent(self)
        toolbar = NavigationToolbar(canvas, self)

        layout = QVBoxLayout()
        layout.addWidget(canvas)
        layout.addWidget(toolbar)
        self.setLayout(layout)

        model.events.title.connect(self._on_title_changed)
        # The FigureSpec model does not currently allow axes to be added or
        # removed, so we do not need to handle changes in model.axes.

    @property
    def axes(self):
        "Read-only access to the mapping AxesSpec UUID -> MatplotlibAxes"
        return DictView(self._axes)

    def _on_title_changed(self, event):
        self.figure.suptitle(event.value)
        self._redraw()

    def _redraw(self):
        "Redraw the canvas."
        # Schedule matplotlib to redraw the canvas at the next opportunity, in
        # a threadsafe fashion.
        self.figure.canvas.draw_idle()


def _make_figure(figure_spec):
    "Create a Figure and Axes."
    matplotlib.use("Qt5Agg")  # must set before importing matplotlib.pyplot
    import matplotlib.pyplot as plt  # noqa

    # TODO Let FigureSpec give different options to subplots here,
    # but verify that number of axes created matches the number of axes
    # specified.
    fig, axes = plt.subplots(len(figure_spec.axes))
    # Handl return type instability in plt.subplots.
    if not isinstance(axes, collections.abc.Iterable):
        axes = [axes]
    return fig, axes
