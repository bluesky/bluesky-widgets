from bluesky_live.run_builder import RunBuilder
import pytest
import numpy

from ..plot_builders import RasteredImages
from ..plot_specs import Axes, Figure


@pytest.fixture
def non_snaking_run():
    # Test data
    md = {"motors": ["y", "x"], "shape": [2, 2], "snaking": (False, False)}
    with RunBuilder(md) as builder:
        builder.add_stream("primary", data={"ccd": [1, 2, 3, 4], "x": [0, 1, 0, 1], "y": [0, 0, 1, 1]})
    run = builder.get_run()
    return run


@pytest.fixture
def snaking_run():
    # Test data
    md = {"motors": ["y", "x"], "shape": [2, 2], "snaking": (False, True)}
    with RunBuilder(md) as builder:
        builder.add_stream("primary", data={"ccd": [1, 2, 3, 4], "x": [0, 1, 1, 0], "y": [0, 0, 1, 1]})
    run = builder.get_run()
    return run


def test_rastered_image(non_snaking_run, FigureView):
    "Test RasteredImages with a 2D array."
    run = non_snaking_run
    model = RasteredImages("ccd", shape=(2, 2))
    view = FigureView(model.figure)
    assert not model.figure.axes[0].artists
    model.add_run(run)
    assert model.figure.axes[0].artists
    view.close()


def test_x_y_positive_change_x_y_limits(non_snaking_run, FigureView):
    "Test x_positive and y_positive change x_limits and y_limits"
    run = non_snaking_run
    model = RasteredImages("ccd", shape=(2, 2), x_positive="left", y_positive="down")
    view = FigureView(model.figure)
    model.add_run(run)
    expected_x_lims = expected_y_lims = (1.5, -0.5)
    assert model.axes.x_limits == expected_x_lims
    assert model.axes.y_limits == expected_y_lims
    model.x_positive = "right"
    model.y_positive = "up"
    expected_x_lims = expected_y_lims = (-0.5, 1.5)
    assert model.axes.x_limits == expected_x_lims
    assert model.axes.y_limits == expected_y_lims
    view.close()


def test_x_y_limits_change_x_y_positive(non_snaking_run, FigureView):
    "Test x_limits and y_limits change x_positive and y_positive"
    run = non_snaking_run
    axes = Axes(x_limits=(1.5, -0.5), y_limits=(1.5, -0.5))
    Figure((axes,), title="")
    model = RasteredImages("ccd", shape=(2, 2), axes=axes)
    view = FigureView(model.figure)
    model.add_run(run)
    assert model.x_positive == "left"
    assert model.y_positive == "down"
    model.axes.x_limits = model.axes.y_limits = (-0.5, 1.5)
    assert model.x_positive == "right"
    assert model.y_positive == "up"
    view.close()


def test_non_snaking_image_data(non_snaking_run, FigureView):
    run = non_snaking_run
    model = RasteredImages("ccd", shape=(2, 2))
    model.add_run(run)
    view = FigureView(model.figure)
    actual_data = model.figure.axes[0].artists[0].update()["array"]
    expected_data = [[1, 2], [3, 4]]
    assert numpy.array_equal(actual_data, expected_data)
    view.close()


def test_snaking_image_data(snaking_run, FigureView):
    run = snaking_run
    model = RasteredImages("ccd", shape=(2, 2))
    view = FigureView(model.figure)
    model.add_run(run)
    actual_data = model.figure.axes[0].artists[0].update()["array"]
    expected_data = [[1, 2], [4, 3]]
    assert numpy.array_equal(actual_data, expected_data)
    view.close()


def test_non_snaking_image_data_positions(FigureView):
    md = {"motors": ["y", "x"], "shape": [2, 2], "snaking": (False, False)}
    model = RasteredImages("ccd", shape=(2, 2))
    view = FigureView(model.figure)
    with RunBuilder(md) as builder:
        ccd = iter([1, 2, 3, 4])
        x = iter([0, 1, 0, 1])
        y = iter([0, 0, 1, 1])
        run = builder.get_run()
        model.add_run(run)
        # First data point
        builder.add_stream("primary", data={"ccd": [next(ccd)], "x": [next(x)], "y": [next(y)]})
        actual_data = model.figure.axes[0].artists[0].update()["array"]
        expected_data = [[1, numpy.nan], [numpy.nan, numpy.nan]]
        assert numpy.array_equal(actual_data, expected_data, equal_nan=True)
        # Second point
        builder.add_data("primary", data={"ccd": [next(ccd)], "x": [next(x)], "y": [next(y)]})
        actual_data = model.figure.axes[0].artists[0].update()["array"]
        expected_data = [[1, 2], [numpy.nan, numpy.nan]]
        assert numpy.array_equal(actual_data, expected_data, equal_nan=True)
        # Third point
        builder.add_data("primary", data={"ccd": [next(ccd)], "x": [next(x)], "y": [next(y)]})
        actual_data = model.figure.axes[0].artists[0].update()["array"]
        expected_data = [[1, 2], [3, numpy.nan]]
        assert numpy.array_equal(actual_data, expected_data, equal_nan=True)
        # Fourth point
        builder.add_data("primary", data={"ccd": [next(ccd)], "x": [next(x)], "y": [next(y)]})
        actual_data = model.figure.axes[0].artists[0].update()["array"]
        expected_data = [[1, 2], [3, 4]]
        assert numpy.array_equal(actual_data, expected_data, equal_nan=True)
    view.close()


def test_snaking_image_data_positions(FigureView):
    md = {"motors": ["y", "x"], "shape": [2, 2], "snaking": (False, True)}
    model = RasteredImages("ccd", shape=(2, 2))
    view = FigureView(model.figure)
    with RunBuilder(md) as builder:
        ccd = iter([1, 2, 3, 4])
        x = iter([0, 1, 1, 0])
        y = iter([0, 0, 1, 1])
        run = builder.get_run()
        model.add_run(run)
        # First data point
        builder.add_stream("primary", data={"ccd": [next(ccd)], "x": [next(x)], "y": [next(y)]})
        actual_data = model.figure.axes[0].artists[0].update()["array"]
        expected_data = [[1, numpy.nan], [numpy.nan, numpy.nan]]
        assert numpy.array_equal(actual_data, expected_data, equal_nan=True)
        # Second point
        builder.add_data("primary", data={"ccd": [next(ccd)], "x": [next(x)], "y": [next(y)]})
        actual_data = model.figure.axes[0].artists[0].update()["array"]
        expected_data = [[1, 2], [numpy.nan, numpy.nan]]
        assert numpy.array_equal(actual_data, expected_data, equal_nan=True)
        # Third point
        builder.add_data("primary", data={"ccd": [next(ccd)], "x": [next(x)], "y": [next(y)]})
        actual_data = model.figure.axes[0].artists[0].update()["array"]
        expected_data = [[1, 2], [numpy.nan, 3]]
        assert numpy.array_equal(actual_data, expected_data, equal_nan=True)
        # Fourth point
        builder.add_data("primary", data={"ccd": [next(ccd)], "x": [next(x)], "y": [next(y)]})
        actual_data = model.figure.axes[0].artists[0].update()["array"]
        expected_data = [[1, 2], [4, 3]]
        assert numpy.array_equal(actual_data, expected_data, equal_nan=True)
    view.close()


def test_figure_set_after_instantiation():
    axes = Axes()
    model = RasteredImages("ccd", shape=(2, 2), axes=axes)
    assert model.figure is None
    figure = Figure((axes,), title="")
    assert model.figure is figure
