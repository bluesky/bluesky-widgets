from bluesky_live.run_builder import RunBuilder

from ...models.plot_specs import FigureSpec, FigureSpecList, AxesSpec, LineSpec
from ..figures import QtFigure, QtFigures


# Generate example data.
with RunBuilder() as builder:
    builder.add_stream("primary", data={"a": [1, 2, 3], "b": [1, 4, 9]})
run = builder.get_run()


def func(run):
    def transform(run):
        ds = run.primary.read()
        return ds["a"], ds["b"]

    line = LineSpec(transform, run, "label")
    axes = AxesSpec(lines=[line], x_label="a", y_label="b")
    figure = FigureSpec((axes,), title="test")
    return figure


def test_figure(qtbot):
    "Basic test: create a QtFigure."
    figure = func(run)
    QtFigure(figure)


def test_figures(qtbot):
    "Basic test: create QtFigures."
    figure = func(run)
    another_figure = func(run)
    figures = FigureSpecList([figure, another_figure])
    QtFigures(figures)
