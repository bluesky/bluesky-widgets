from bluesky_live.run_builder import build_simple_run
import numpy

from ..plot_builders import Images


def test_image():
    "Test Images with a 2D array."
    run = build_simple_run({"ccd": numpy.random.random((11, 13))})
    model = Images("ccd")
    assert not model.figure.axes[0].images
    model.add_run(run)
    assert model.figure.axes[0].images


def test_image_reduction():
    "Test Images with higher-dimensional arrays."
    dims = (5, 7, 11, 13, 17, 19)
    for i in range(3, len(dims)):
        run = build_simple_run({"ccd": numpy.random.random(dims[:i])})
    model = Images("ccd")
    model.add_run(run)


def test_properties():
    "Touch various accessors"
    run = build_simple_run({"ccd": numpy.random.random((11, 13))})
    model = Images("c * ccd", namespace={"c": 3})
    model.add_run(run)
    assert model.runs[0] is run
    assert model.field == "c * ccd"
    assert dict(model.namespace) == {"c": 3}
    assert model.needs_streams == ("primary",)
