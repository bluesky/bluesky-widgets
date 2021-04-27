import collections.abc
from pathlib import Path
import matplotlib

from ..models.plot_specs import Figure, FigureList
from .._matplotlib_axes import MatplotlibAxes
from ..utils.dict_view import DictView


class HeadlessFigures:
    """
    A headless "view" for a FigureList model.

    It does not produce a graphical user interface. Instead, it provides
    methods for exporting figures as images.

    Examples
    --------

    Export all the figures to a directory. They will be named by their title.
    If there are duplciate titles, a counting number will appended like
    x-1.png, x-2.png.

    >>> headless = HeadlessFigures(model)
    >>> headless.export_all("path/to/directory/")

    Control the format.

    >>> headless.export_all("path/to/directory/", format="png")
    >>> headless.export_all("path/to/directory/", format="jpg")
    """

    def __init__(self, model: FigureList):

        self.model = model
        # Map Figure UUID to widget with HeadlessFigure
        self._figures = {}

        for figure_spec in model:
            self._add_figure(figure_spec)
        model.events.added.connect(self._on_figure_added)
        model.events.removed.connect(self._on_figure_removed)

    @property
    def figures(self):
        "Read-only access to the mapping Figure UUID -> HeadlessFigure"
        return DictView(self._figures)

    def _on_figure_added(self, event):
        figure_spec = event.item
        self._add_figure(figure_spec)

    def _add_figure(self, figure_spec):
        "Create a new matplotlib Figure."
        figure = HeadlessFigure(figure_spec)
        self._figures[figure_spec.uuid] = figure

    def _on_figure_removed(self, event):
        "Remove the associated tab and close its canvas."
        figure_spec = event.item
        figure = self._figures[figure_spec.uuid]
        figure.close_figure()
        del self._figures[figure_spec.uuid]

    def close_figures(self):
        for figure in self._figures.values():
            figure.close_figure()

    close = close_figures

    def export_all(self, directory, format="png", **kwargs):
        """
        Export all figures.

        Parameters
        ----------
        directory : str | Path
        format : str, optional
            Default is "png".
        **kwargs :
            Passed through to matplotlib.figure.Figure.savefig

        Returns
        -------
        filenames : List[String]
        """
        # Avoid name collisions in the case of duplicate titles by appending
        # "-1", "-2", "-3", ... to duplicates.
        titles_tallied = {}
        filenames = []
        for figure_spec in self.model:
            title = figure_spec.title
            if title in titles_tallied:
                filename = f"{title}-{titles_tallied[title]}"
                titles_tallied[title] += 1
            else:
                filename = title
                titles_tallied[title] = 1
            filename = str(Path(directory, f"{filename}.{format}"))
            figure = self._figures[figure_spec.uuid]
            figure.export(filename, format=format, **kwargs)
            filenames.append(filename)
        return filenames


class HeadlessFigure:
    """
    A Headless "view" for a Figure model. This always contains one Figure.

    Examples
    --------

    Export the figure.

    >>> headless = HeadlessFigure(model)
    >>> headless.export("my-figure.png")
    """

    def __init__(self, model: Figure):
        self.model = model
        self.figure, self.axes_list = _make_figure(model)
        self.figure.suptitle(model.title)
        self._axes = {}
        for axes_spec, axes in zip(model.axes, self.axes_list):
            self._axes[axes_spec.uuid] = MatplotlibAxes(model=axes_spec, axes=axes)

        model.events.title.connect(self._on_title_changed)
        # The Figure model does not currently allow axes to be added or
        # removed, so we do not need to handle changes in model.axes.

    @property
    def axes(self):
        "Read-only access to the mapping Axes UUID -> MatplotlibAxes"
        return DictView(self._axes)

    def _on_title_changed(self, event):
        self.figure.suptitle(event.value)

    def close_figure(self):
        _close_figure(self.figure)

    close = close_figure

    def export(self, filename, format="png", **kwargs):
        """
        Export figure.

        Parameters
        ----------
        filename : str | Path
        format : str, optional
            Default is "png".
        **kwargs :
            Passed through to matplotlib.figure.Figure.savefig
        """
        self.figure.savefig(str(filename), format=format, **kwargs)


def _make_figure(figure_spec):
    "Create a Figure and Axes."
    matplotlib.use("Agg")  # must set before importing matplotlib.pyplot
    import matplotlib.pyplot as plt  # noqa

    # TODO Let Figure give different options to subplots here,
    # but verify that number of axes created matches the number of axes
    # specified.
    fig, axes = plt.subplots(len(figure_spec.axes))
    # Handl return type instability in plt.subplots.
    if not isinstance(axes, collections.abc.Iterable):
        axes = [axes]
    return fig, axes


def _close_figure(figure):
    """
    Workaround for matplotlib regression relating to closing figures in Agg

    See https://github.com/matplotlib/matplotlib/pull/18184/
    """
    # TODO It would be better to switch the approach based on matplotlib
    # versions known to have this problem, rather than blindly trying. Update
    # this once a fixed has been released and we know the earliest version of
    # matplotlib that does not have this bug.
    try:
        figure.canvas.close()
    except AttributeError:
        from matplotlib._pylab_helpers import Gcf

        num = next(
            (manager.num for manager in Gcf.figs.values() if manager.canvas.figure == figure),
            None,
        )
        if num is not None:
            Gcf.destroy(num)
