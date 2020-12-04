from bluesky_live.run_builder import RunBuilder
import pytest

from ...models.plot_specs import (
    FigureSpec,
    FigureSpecList,
    AxesSpec,
    LineSpec,
    ImageSpec,
)
from ..figures import QtFigure, QtFigures


# Generate example data.
with RunBuilder() as builder:
    builder.add_stream("primary", data={"a": [1, 2, 3], "b": [1, 4, 9]})
run = builder.get_run()


def transform(run):
    ds = run.primary.read()
    return ds["a"], ds["b"]


def func(run):
    line = LineSpec(transform, run, "label")
    axes = AxesSpec(lines=[line], x_label="a", y_label="b", title="axes title")
    figure = FigureSpec((axes,), title="figure title")
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


def test_figure_title_syncing(qtbot):
    model = func(run)
    view = QtFigure(model)
    initial = model.title
    assert view.figure._suptitle.get_text() == initial
    expected = "figure title changed"
    model.title = expected
    assert model.title == expected
    # Is there no public matplotlib API for this?
    # https://stackoverflow.com/a/48917679
    assert view.figure._suptitle.get_text() == expected


def test_short_title_syncing(qtbot):
    model = func(run)
    figures = FigureSpecList([model])
    view = QtFigures(figures)
    actual_title = view.figures[model.uuid].figure._suptitle.get_text()
    assert view.tabText(0) == actual_title
    expected_short_title = "new short title"
    model.short_title = expected_short_title
    assert model.short_title == expected_short_title
    actual_title = view.figures[model.uuid].figure._suptitle.get_text()
    assert view.tabText(0) == expected_short_title
    assert actual_title == model.title
    expected_title = "new title"
    model.title = expected_title
    assert view.tabText(0) == model.short_title
    model.short_title = None
    assert view.tabText(0) == expected_title


def test_non_null_short_title_syncing(qtbot):
    model = func(run)
    model.short_title = "short title"
    figures = FigureSpecList([model])
    view = QtFigures(figures)
    actual_title = view.figures[model.uuid].figure._suptitle.get_text()
    assert view.tabText(0) == model.short_title
    assert actual_title == model.title


@pytest.mark.parametrize(
    ("model_property", "mpl_method"),
    [("title", "get_title"), ("x_label", "get_xlabel"), ("y_label", "get_ylabel")],
)
def test_axes_syncing(qtbot, model_property, mpl_method):
    model = func(run)
    view = QtFigure(model)
    initial = getattr(model.axes[0], model_property)
    assert getattr(view.figure.axes[0], mpl_method)() == initial
    expected = "axes title changed"
    setattr(model.axes[0], model_property, expected)
    assert getattr(model.axes[0], model_property) == expected
    assert getattr(view.figure.axes[0], mpl_method)() == expected


def test_axes_set_figure():
    "Adding axes to a figure sets their figure."
    axes = AxesSpec()
    assert axes.figure is None
    figure = FigureSpec((axes,), title="figure title")
    assert axes.figure is figure
    # Once axes belong to a figure, they cannot belong to another figure.
    with pytest.raises(RuntimeError):
        FigureSpec((axes,), title="figure title")

    with pytest.raises(AttributeError):
        figure.axes = (axes,)  # not settable


artist_set_axes_params = pytest.mark.parametrize(
    ("model_property", "artist_factory"),
    [
        ("lines", lambda: LineSpec(transform, run, "label")),
        ("images", lambda: ImageSpec(transform, run, "label")),
    ],
    ids=["lines", "images"],
)


@artist_set_axes_params
def test_artist_set_axes_at_init(model_property, artist_factory):
    "Adding an artist to axes at init time sets its axes."
    artist = artist_factory()
    axes = AxesSpec(**{model_property: [artist]})
    assert artist in getattr(axes, model_property)
    assert artist in axes.by_uuid.values()
    assert artist.axes is axes

    # Once line belong to a axes, it cannot belong to another axes.
    with pytest.raises(RuntimeError):
        AxesSpec(**{model_property: [artist]})


@artist_set_axes_params
def test_artist_set_axes_after_init(model_property, artist_factory):
    "Adding an artist to axes after init time sets its axes."
    artist = artist_factory()
    axes = AxesSpec()
    getattr(axes, model_property).append(artist)
    assert artist in getattr(axes, model_property)
    assert artist in axes.by_uuid.values()
    assert artist.axes is axes

    # Once line belong to a axes, it cannot belong to another axes.
    with pytest.raises(RuntimeError):
        AxesSpec(**{model_property: [artist]})
