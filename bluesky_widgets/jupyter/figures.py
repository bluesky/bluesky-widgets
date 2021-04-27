from ipywidgets import widgets
import ipympl.backend_nbagg
import matplotlib.figure

from ..models.plot_specs import Figure, FigureList
from .._matplotlib_axes import MatplotlibAxes as _MatplotilbAxes
from ..utils.dict_view import DictView


def _initialize_mpl():
    "Set backend to ipympl and import pyplot."
    import matplotlib

    matplotlib.use("module://ipympl.backend_nbagg")  # must set before importing matplotlib.pyplot
    # must import matplotlib.pyplot here because bluesky.utils.during_task
    # expects it to be imported
    import matplotlib.pyplot as plt  # noqa


class JupyterAxes(_MatplotilbAxes):
    # We need to turn `draw_idle` into "draw now" because the way
    # that `draw_idle` is implemented requires a round-trip
    # communication with the js front end (from the Python side we say
    # "dear JS, when you want you to ask us for an update".  The JS then
    # sends back a message asking for the the figure to be rendered.
    # This means we will not overload the frontend with more updates
    # than it wants.
    #
    # However, when a notebook cell is executing, the zmq loop that
    # processes messages from the front end is blocked so we never see
    # the request for a re-draw. The figure looks "dead".
    #
    # We do not see this problem with Qt because the default "during
    # task" of the RunEngine spins the Qt event loop while we wait on the
    # `_run` task in a background thread so the `draw_idle`
    # implementation throws a signal on the Qt event loop which gets
    # promptly serviced.  In contrast, the default during task when
    # the RE is in the notebook is event.wait which simply blocks
    # until the `_run` task finishes, hence the "broken" behavior.
    def draw_idle(self):
        self.axes.figure.canvas.draw()


class JupyterFigures(widgets.Tab):
    """
    A Jupyter (ipywidgets) view for a FigureList model.
    """

    def __init__(self, model: FigureList, *args, **kwargs):
        _initialize_mpl()
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
        "Read-only access to the mapping Figure UUID -> JupyterFigure"
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
    A Jupyter view for a Figure model. This always contains one Figure.
    """

    def __init__(self, model: Figure):
        _initialize_mpl()
        super().__init__()
        self.model = model
        self.figure = matplotlib.figure.Figure()
        # TODO Let Figure give different options to subplots here,
        # but verify that number of axes created matches the number of axes
        # specified.
        self.axes_list = list(self.figure.subplots(len(model.axes), squeeze=False).ravel())
        self.figure.suptitle(model.title)
        self._axes = {}
        for axes_spec, axes in zip(model.axes, self.axes_list):
            self._axes[axes_spec.uuid] = JupyterAxes(model=axes_spec, axes=axes)
        # This updates the Figure's internal state, setting its canvas.
        canvas = ipympl.backend_nbagg.Canvas(self.figure)
        label = "Figure"
        # this will stash itself on the canvas
        ipympl.backend_nbagg.FigureManager(canvas, 0)
        self.figure.set_label(label)
        self.children = (self.figure.canvas,)

        model.events.title.connect(self._on_title_changed)

        # By "resizing" (even without actually changing the size) we bump the
        # ipympl machinery that sets up frontend--backend communication and
        # starting displaying data from the figure. Without this, the figure
        # *widget* displays instantly but the actual *plot* (the PNG data sent from
        # matplotlib) is not displayed until cell execution completes.
        _, _, width, height = self.figure.bbox.bounds
        self.figure.canvas.manager.resize(width, height)
        self.figure.canvas.draw_idle()

        # The Figure model does not currently allow axes to be added or
        # removed, so we do not need to handle changes in model.axes.

    @property
    def axes(self):
        "Read-only access to the mapping Axes UUID -> JupyterAxes"
        return DictView(self._axes)

    def _on_title_changed(self, event):
        self.figure.suptitle(event.value)
        self._redraw()

    def _redraw(self):
        "Redraw the canvas."
        self.figure.canvas.draw()

    def close_figure(self):
        self.figure.canvas.close()


class _JupyterFigureTab(widgets.HBox):
    """
    A tab in a widgets.Tab container that contains a JupyterFigure.

    This is aware of its parent in order to support tab-closing.
    """

    def __init__(self, model: Figure, parent):
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
        "Read-only access to the mapping Axes UUID -> JupyterAxes"
        return DictView(self._jupyter_figure.axes)
