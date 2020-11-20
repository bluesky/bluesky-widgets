import collections.abc
import gc

from ipywidgets import widgets
import matplotlib

from ..models.plot_specs import FigureSpec, FigureSpecList
from .._plot_axes import Axes


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
        self._add_figure(figure_spec)

    def _add_figure(self, figure_spec):
        "Add a new tab with a matplotlib Figure."
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
        "Remove the associated tab and close its canvas."
        figure_spec = event.item
        widget = self._figures[figure_spec.uuid]
        children = list(self.children)
        children.remove(widget)
        self.children = tuple(children)
        widget.figure.canvas.close()
        del widget
        del self._figures[figure_spec.uuid]
        gc.collect()

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
        self._axes = {}
        for axes_spec, axes in zip(model.axes, self.axes_list):
            self._axes[axes_spec.uuid] = Axes(model=axes_spec, axes=axes)
        self.children = (self.figure.canvas,)

        # The FigureSpec model does not currently allow axes to be added or
        # removed, so we do not need to handle changes in model.axes.


class _JupyterFigureTab(widgets.HBox):
    """
    A tab in a widgets.Tab container that contains a JupyterFigure.

    This is aware of its parent in order to support tab-closing.
    """

    def __init__(self, model: FigureSpec, parent):
        super().__init__()
        self.parent = parent
        self.button = widgets.Button(description="Close")
        self.button.on_click(lambda _: self.parent.on_close_tab_requested(self.model))
        self.jupyter_figure = JupyterFigure(model)
        self.children = (self.jupyter_figure, self.button)


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
