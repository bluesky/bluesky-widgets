from bluesky_live.run_builder import build_simple_run
import numpy

from ..plot_builders import Image


def test_image():
    "Test Image with a 2D array."
    run = build_simple_run({"ccd": numpy.random.random((11, 13))})
    model = Image("ccd")
    assert not model.figure.axes[0].images
    model.run = run
    assert model.figure.axes[0].images


def test_image_reduction():
    "Test Image with higher-dimensional arrays."
    dims = (5, 7, 11, 13, 17, 19)
    for i in range(3, len(dims)):
        run = build_simple_run({"ccd": numpy.random.random(dims[:i])})
    model = Image("ccd")
    model.run = run


def test_properties():
    "Touch various accessors"
    run = build_simple_run({"ccd": numpy.random.random((11, 13))})
    model = Image("c * ccd", namespace={"c": 3})
    model.run = run
    assert model.run is run
    assert model.field == "c * ccd"
    assert dict(model.namespace) == {"c": 3}
    assert model.needs_streams == ("primary",)
