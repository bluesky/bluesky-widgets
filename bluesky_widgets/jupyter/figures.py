import collections.abc

from ipywidgets import widgets
import matplotlib

from ..models.plot_specs import FigureSpec, FigureSpecList
from .._matplotlib_axes import MatplotlibAxes
from ..utils.dict_view import DictView


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

    @property
    def figures(self):
        "Read-only access to the mapping FigureSpec UUID -> JupyterFigure"
        return DictView(self._figures)

    def _on_figure_added(self, event):
        figure_spec = event.item
        self._add_figure(figure_spec)

    def _add_figure(self, figure_spec):
        "Add a new tab with a matplotlib Figure."
        tab = _JupyterFigureTab(figure_spec, parent=self)
        self._figures[figure_spec.uuid] = tab
        self.children = (*self.children, tab)
        index = len(self.children) - 1
        self.set_title(index, figure_spec.title)
        figure_spec.events.title.connect(self._on_title_changed)
        figure_spec.events.short_title.connect(self._on_short_title_changed)
        # Workaround: If the tabs are cleared and then children are added
        # again, no tab is selected.
        if index == 0:
            self.selected_index = 0

    def _on_figure_removed(self, event):
        "Remove the associated tab and close its canvas."
        figure_spec = event.item
        widget = self._figures[figure_spec.uuid]
        children = list(self.children)
        children.remove(widget)
        self.children = tuple(children)
        widget.close_figure()
        del self._figures[figure_spec.uuid]

    def _on_short_title_changed(self, event):
        "This sets the tab title."
        figure_spec = event.figure_spec
        widget = self._figures[figure_spec.uuid]
        index = self.children.index(widget)
        # Fall back to title if short_title is being unset.
        if event.value is None:
            self.set_title(index, figure_spec.title)
        else:
            self.set_title(index, event.value)

    def _on_title_changed(self, event):
        "This sets the tab title only if short_title is None."
        figure_spec = event.figure_spec
        if figure_spec.short_title is None:
            widget = self._figures[figure_spec.uuid]
            index = self.children.index(widget)
            self.set_title(index, event.value)

    def on_close_tab_requested(self, model):
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
        self.figure.suptitle(model.title)
        self._axes = {}
        for axes_spec, axes in zip(model.axes, self.axes_list):
            self._axes[axes_spec.uuid] = MatplotlibAxes(model=axes_spec, axes=axes)
        self.children = (self.figure.canvas,)

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

    def close_figure(self):
        self.figure.canvas.close()


class _JupyterFigureTab(widgets.HBox):
    """
    A tab in a widgets.Tab container that contains a JupyterFigure.

    This is aware of its parent in order to support tab-closing.
    """

    def __init__(self, model: FigureSpec, parent):
        super().__init__()
        self.model = model
        self.parent = parent
        self.button = widgets.Button(description="Close")
        self.button.on_click(lambda _: self.parent.on_close_tab_requested(self.model))
        self._jupyter_figure = JupyterFigure(model)
        self.children = (self._jupyter_figure, self.button)

        # Pass-through accessors to match the API of QtFigure, which has/needs
        # one less layer.
        self.figure = self._jupyter_figure.figure

    def close_figure(self):
        # Pass through toe JupyterFigure instance.
        return self._jupyter_figure.close_figure()

    @property
    def axes(self):
        "Read-only access to the mapping AxesSpec UUID -> MatplotlibAxes"
        return DictView(self._jupyter_figure.axes)


def _make_figure(figure_spec):
    "Create a Figure and Axes."
    matplotlib.use(
        "module://ipympl.backend_nbagg"
    )  # must set before importing matplotlib.pyplot
    import matplotlib.pyplot as plt  # noqa

    # By default, with interactive mode on, each fig.show() will be called
    # automatically, and we'll get duplicates littering the output area. We
    # only want to see the figures where they are placed explicitly in widgets.
    plt.ioff()

    # TODO Let FigureSpec give different options to subplots here,
    # but verify that number of axes created matches the number of axes
    # specified.
    figure, axes = plt.subplots(len(figure_spec.axes))
    figure.tight_layout()
    # Handle return type instability in plt.subplots.
    if not isinstance(axes, collections.abc.Iterable):
        axes = [axes]
    return figure, axes
