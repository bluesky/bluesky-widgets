from bluesky_live.run_builder import RunBuilder
import pytest

from ..plot_builders import RasteredImage
from ..plot_specs import AxesSpec


@pytest.fixture
def non_snaking_run():
    # Test data
    md = {'motors': ['y', 'x'], 'shape': [2, 2], 'snaking': (False, False)}
    with RunBuilder(md) as builder:
        builder.add_stream("primary", data={"ccd": [1, 2, 3, 4],
                                            'x': [0, 1, 0, 1],
                                            'y': [0, 0, 1, 1]})
    run = builder.get_run()
    return run


@pytest.fixture
def snaking_run():
    # Test data
    md = {'motors': ['y', 'x'], 'shape': [2, 2], 'snaking': (False, True)}
    with RunBuilder(md) as builder:
        builder.add_stream("primary", data={"ccd": [1, 2, 3, 4],
                                            'x': [0, 1, 1, 0],
                                            'y': [0, 0, 1, 1]})
    run = builder.get_run()
    return run


def test_rastered_image(non_snaking_run):
    "Test RasteredImage with a 2D array."
    run = non_snaking_run
    model = RasteredImage("ccd", shape=(2, 2))
    assert not model.figure.axes[0].images
    model.run = run
    assert model.figure.axes[0].images


def test_x_y_positive_change_x_y_limits(non_snaking_run):
    "Test x_positive and y_positive change x_limits and y_limits"
    run = non_snaking_run
    model = RasteredImage("ccd", shape=(2, 2),
                          x_positive='left', y_positive='down')
    model.run = run
    expected_x_lims = expected_y_lims = (1.5, -0.5)
    assert model.axes.x_limits == expected_x_lims
    assert model.axes.y_limits == expected_y_lims
    model.x_positive = 'right'
    model.y_positive = 'up'
    expected_x_lims = expected_y_lims = (-0.5, 1.5)
    assert model.axes.x_limits == expected_x_lims
    assert model.axes.y_limits == expected_y_lims


def test_x_y_limits_change_x_y_positive(non_snaking_run):
    "Test x_limits and y_limits change x_positive and y_positive"
    run = non_snaking_run
    axes = AxesSpec(x_limits=(1.5, -0.5), y_limits=(1.5, -0.5))
    model = RasteredImage("ccd", shape=(2, 2), axes=axes)
    model.run = run
    assert model.x_positive == 'left'
    assert model.y_positive == 'down'
    model.axes.x_limits = model.axes.y_limits = (-0.5, 1.5)
    assert model.x_positive == 'right'
    assert model.y_positive == 'up'


def test_non_snaking_image_data(non_snaking_run):
    run = non_snaking_run
    model = RasteredImage("ccd", shape=(2, 2))
    model.run = run
    actual_data = model.figure.axes[0].images[0].func(run)
    expected_data = [[1, 2], [3, 4]]
    assert (actual_data == expected_data).all()


def test_snaking_image_data(snaking_run):
    run = snaking_run
    model = RasteredImage("ccd", shape=(2, 2))
    model.run = run
    actual_data = model.figure.axes[0].images[0].func(run)
    expected_data = [[1, 2], [4, 3]]
    assert (actual_data == expected_data).all()
