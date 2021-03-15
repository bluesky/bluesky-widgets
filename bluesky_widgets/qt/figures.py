import gc

from qtpy.QtWidgets import (
    QSizePolicy,
    QTabWidget,
    QWidget,
    QVBoxLayout,
)
from qtpy.QtCore import Signal, QObject
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
import matplotlib.figure

from ..models.plot_specs import Figure, FigureList
from .._matplotlib_axes import MatplotlibAxes
from ..utils.event import Event
from ..utils.dict_view import DictView


def _initialize_matplotlib():
    "Set backend to Qt5Agg and import pyplot."
    import matplotlib

    matplotlib.use("Qt5Agg")  # must set before importing matplotlib.pyplot
    import matplotlib.pyplot  # noqa

def convert_axes_to_host_axes(axes):
    fig = axes.get_figure()
    rect = axes._position
    return HostAxes(fig, rect)


def init_host(host, data, label):
    host.set_ylabel(label)
    host.axis["right"].set_visible(False)
    p, = host.plot(range(len(data)), data, label=label)
    host.axis["left"].label.set_color(p.get_color())
    return (p, )

def init_host_twinx(host, label):
    #host.set_ylabel(label)
    host.figure.subplots_adjust(right=.75)
    host.spines["right"].set_visible(False)
    #p, = host.plot(range(len(data)), data, c=np.random.rand(3,), label=label)
    #host.yaxis.label.set_color(p.get_color())
    #return (p, )
    return host
	
	

def add_parasite(host, data, label, offset):
    par = ParasiteAxes(host, sharex=host)
    host.parasites.append(par)
    par.set_ylabel(label)
    offset = (offset, 0)
    new_axisline = par.get_grid_helper().new_fixed_axis
    par.axis["right3"] = new_axisline(loc="right", axes=par, offset=offset)
    p, = par.plot(range(len(data)), data, label=label)
    par.set_ylim(*par.get_ylim()) # axes don't draw until resize without this - not sure why
    par.axis["right3"].label.set_color(p.get_color())
    return (p,)

def make_patch_spines_invisible(ax):
    ax.set_frame_on(True)
    ax.patch.set_visible(False)
    for sp in ax.spines.values():
        sp.set_visible(False)

def add_parasite_twinx(host, label, axis_num):
    par = host.twinx()
    #par.set_ylabel(label)
    if axis_num > 0:
        n = axis_num
        par.spines["right"].set_position(("axes", 1+n*.14))
        make_patch_spines_invisible(par)
        par.spines["right"].set_visible(True)
    #p, = par.plot(range(len(data)), data, c=np.random.rand(3,), label=label)
    par.set_ylim(*par.get_ylim()) # axes don't draw until resize without this - not sure why
    #par.yaxis.label.set_color(p.get_color())
    #print(par.lines[0], p)
    #print(dir(par))
    #return (p,)
    return par




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
    A Jupyter (ipywidgets) view for a FigureList model.
    """

    __callback_event = Signal(object, Event)

    def __init__(self, model: FigureList, parent=None):
        _initialize_matplotlib()
        super().__init__(parent)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._on_close_tab_requested)
        self.resize(self.sizeHint())

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

    def sizeHint(self):
        size_hint = super().sizeHint()
        size_hint.setWidth(700)
        size_hint.setHeight(500)
        return size_hint

    @property
    def figures(self):
        "Read-only access to the mapping Figure UUID -> QtFigure"
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
        self.addTab(tab, figure_spec.short_title or figure_spec.title)
        self._figures[figure_spec.uuid] = tab
        # Update the tab title when short_title changes (or, if short_title is
        # None, when title changes).
        self._threadsafe_connect(figure_spec.events.title, self._on_title_changed)
        self._threadsafe_connect(
            figure_spec.events.short_title, self._on_short_title_changed
        )

    def _on_figure_removed(self, event):
        "Remove the associated tab and close its canvas."
        figure_spec = event.item
        widget = self._figures[figure_spec.uuid]
        index = self.indexOf(widget)
        self.removeTab(index)
        widget.close_figure()
        del widget
        gc.collect()
        del self._figures[figure_spec.uuid]

    def _on_short_title_changed(self, event):
        "This sets the tab title."
        figure_spec = event.figure_spec
        widget = self._figures[figure_spec.uuid]
        index = self.indexOf(widget)
        # Fall back to title if short_title is being unset.
        if event.value is None:
            self.setTabText(index, figure_spec.title)
        else:
            self.setTabText(index, event.value)

    def _on_title_changed(self, event):
        "This sets the tab title only if short_title is None."
        figure_spec = event.figure_spec
        if figure_spec.short_title is None:
            widget = self._figures[figure_spec.uuid]
            index = self.indexOf(widget)
            self.setTabText(index, event.value)

class QtFigure(QWidget):
    """
    A Qt view for a Figure model. This always contains one Figure.
    """

    def __init__(self, model: Figure, parent=None):
        _initialize_matplotlib()
        super().__init__(parent)
        self.model = model
        self.figure = matplotlib.figure.Figure()
        # TODO Let Figure give different options to subplots here,
        # but verify that number of axes created matches the number of axes
        # specified.
        #if model.parasite:
        #   self.axes_list =  model.axes
        #else:
        if model.parasite:
            #axes = *self.figure.subplots(1, squeeze=False).ravel()
            self.axes_list = [self.figure.add_subplot() for i in range(len(model.axes))]
            #host = init_host_twinx(self.axes_list[0], model.axes[0])
            host = init_host_twinx(self.axes_list[0], model.axes[0].title)
            #host = init_host_twinx(axes, model.axes[0])
            print("model axes num"+str(len(self.model.axes)))
            print("model axes num"+str(len(self.model.axes[0].artists)))
            parasite_list = [add_parasite_twinx(host, axes_spec.title, i) for axes_spec, i in zip(model.axes[1:], list(range(len(model.axes)))[1:])]
            self.axes_list = [host] + parasite_list
        else:

            self.axes_list = list(
                self.figure.subplots(len(model.axes), squeeze=False).ravel()
            )

        self.figure.suptitle(model.title)
        self._axes = {}
        for axes_spec, axes in zip(model.axes, self.axes_list):
            print("get ylabel: " + axes.get_ylabel())
            self._axes[axes_spec.uuid] = ThreadsafeMatplotlibAxes(
                model=axes_spec, axes=axes
            )
        canvas = FigureCanvas(self.figure)
        canvas.setMinimumWidth(640)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        canvas.updateGeometry()
        canvas.setParent(self)
        toolbar = NavigationToolbar(canvas, parent=self)

        layout = QVBoxLayout()
        layout.addWidget(canvas)
        layout.addWidget(toolbar)
        self.setLayout(layout)
        self.resize(self.sizeHint())

        model.events.title.connect(self._on_title_changed)
        # The Figure model does not currently allow axes to be added or
        # removed, so we do not need to handle changes in model.axes.

    def sizeHint(self):
        size_hint = super().sizeHint()
        size_hint.setWidth(700)
        size_hint.setHeight(500)
        return size_hint

    @property
    def axes(self):
        "Read-only access to the mapping Axes UUID -> MatplotlibAxes"
        return DictView(self._axes)

    def _on_title_changed(self, event):
        self.figure.suptitle(event.value)
        self._redraw()

    def _redraw(self):
        "Redraw the canvas."
        # Schedule matplotlib to redraw the canvas at the next opportunity, in
        # a threadsafe fashion.
        self.figure.canvas.draw_idle()

    def close_figure(self):
        self.figure.canvas.close()
