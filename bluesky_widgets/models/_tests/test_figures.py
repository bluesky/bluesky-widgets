from bluesky_live.run_builder import RunBuilder
from bluesky_live.event import CallbackException
import pytest

from ...models.plot_specs import (
    AxesAlreadySet,
    Figure,
    FigureList,
    Axes,
    Line,
    Image,
)


# Generate example data.
with RunBuilder() as builder:
    builder.add_stream("primary", data={"a": [1, 2, 3], "b": [1, 4, 9]})
run = builder.get_run()


def transform(run):
    ds = run.primary.read()
    return {"x": ds["a"], "y": ds["b"]}


def func(run):
    line = Line.from_run(transform, run, "label")
    axes = Axes(artists=[line], x_label="a", y_label="b", title="axes title")
    figure = Figure((axes,), title="figure title")
    return figure


def test_figure(FigureView):
    "Basic test: create a FigureView."
    figure = func(run)
    FigureView(figure)


def test_figures(FigureViews):
    "Basic test: create FigureViews."
    figure = func(run)
    another_figure = func(run)
    figures = FigureList([figure, another_figure])
    FigureViews(figures)


def test_figure_title_syncing(FigureView):
    model = func(run)
    view = FigureView(model)
    initial = model.title
    assert view.figure._suptitle.get_text() == initial
    expected = "figure title changed"
    model.title = expected
    assert model.title == expected
    # Is there no public matplotlib API for this?
    # https://stackoverflow.com/a/48917679
    assert view.figure._suptitle.get_text() == expected


def test_short_title_syncing(FigureViews, request):
    QtFigures = pytest.importorskip("bluesky_widgets.qt.figures.QtFigures")
    if request.getfixturevalue("FigureViews") is not QtFigures:
        pytest.skip("This tests details of the QtFigures view.")
    model = func(run)
    figures = FigureList([model])
    view = FigureViews(figures)
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


def test_non_null_short_title_syncing(FigureViews, request):
    QtFigures = pytest.importorskip("bluesky_widgets.qt.figures.QtFigures")
    if request.getfixturevalue("FigureViews") is not QtFigures:
        pytest.skip("This tests details of the QtFigures view.")
    model = func(run)
    model.short_title = "short title"
    figures = FigureList([model])
    view = FigureViews(figures)
    actual_title = view.figures[model.uuid].figure._suptitle.get_text()
    assert view.tabText(0) == model.short_title
    assert actual_title == model.title


@pytest.mark.parametrize(
    ("model_property", "mpl_method"),
    [("title", "get_title"), ("x_label", "get_xlabel"), ("y_label", "get_ylabel")],
)
def test_axes_syncing(FigureView, model_property, mpl_method):
    model = func(run)
    view = FigureView(model)
    initial = getattr(model.axes[0], model_property)
    assert getattr(view.figure.axes[0], mpl_method)() == initial
    expected = "axes title changed"
    setattr(model.axes[0], model_property, expected)
    assert getattr(model.axes[0], model_property) == expected
    assert getattr(view.figure.axes[0], mpl_method)() == expected


def test_axes_set_figure():
    "Adding axes to a figure sets their figure."
    axes = Axes()
    assert axes.figure is None
    figure = Figure((axes,), title="figure title")
    assert axes.figure is figure
    # Once axes belong to a figure, they cannot belong to another figure.
    with pytest.raises(RuntimeError):
        Figure((axes,), title="figure title")

    with pytest.raises(AttributeError):
        figure.axes = (axes,)  # not settable


artist_set_axes_params = pytest.mark.parametrize(
    "artist_factory",
    # These are factories because each artist can only be assigned to Axes once
    # in its lifecycle. For each test that these params are used in, we need a
    # fresh instance.
    [
        lambda: Line.from_run(transform, run, "label"),
        lambda: Image.from_run(transform, run, "label"),
    ],
    ids=["lines", "images"],
)


@artist_set_axes_params
def test_artist_set_axes_at_init(artist_factory):
    "Adding an artist to axes at init time sets its axes."
    artist = artist_factory()
    axes = Axes(artists=[artist])
    assert artist in axes.artists
    assert artist in axes.by_uuid.values()
    assert artist.axes is axes

    # Once line belong to a axes, it cannot belong to another axes.
    with pytest.raises(CallbackException) as exc_info:
        Axes(artists=[artist])
    exc = exc_info.value
    assert hasattr(exc, "__cause__") and isinstance(exc.__cause__, AxesAlreadySet)


@artist_set_axes_params
def test_artist_set_axes_after_init(artist_factory):
    "Adding an artist to axes after init time sets its axes."
    artist = artist_factory()
    axes = Axes()
    axes.artists.append(artist)
    assert artist in axes.artists
    assert artist in axes.by_uuid.values()
    assert artist.axes is axes

    # Once line belong to a axes, it cannot belong to another axes.
    with pytest.raises(CallbackException) as exc_info:
        Axes(artists=[artist])
    exc = exc_info.value
    assert hasattr(exc, "__cause__") and isinstance(exc.__cause__, AxesAlreadySet)
