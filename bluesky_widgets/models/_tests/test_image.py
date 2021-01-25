from bluesky_live.run_builder import build_simple_run
import numpy

from ..plot_builders import Images
from ..plot_specs import Axes, Figure


def test_image(FigureView):
    "Test Images with a 2D array."
    run = build_simple_run({"ccd": numpy.random.random((11, 13))})
    model = Images("ccd")
    view = FigureView(model.figure)
    assert not model.figure.axes[0].artists
    model.add_run(run)
    assert model.figure.axes[0].artists
    view.close()


def test_image_reduction(FigureView):
    "Test Images with higher-dimensional arrays."
    dims = (5, 7, 11, 13, 17, 19)
    for i in range(3, len(dims)):
        run = build_simple_run({"ccd": numpy.random.random(dims[:i])})
    model = Images("ccd")
    view = FigureView(model.figure)
    model.add_run(run)
    view.close()


def test_properties(FigureView):
    "Touch various accessors"
    run = build_simple_run({"ccd": numpy.random.random((11, 13))})
    model = Images("c * ccd", namespace={"c": 3})
    view = FigureView(model.figure)
    model.add_run(run)
    assert model.runs[0] is run
    assert model.field == "c * ccd"
    assert dict(model.namespace) == {"c": 3}
    assert model.needs_streams == ("primary",)
    view.close()


def test_figure_set_after_instantiation(FigureView):
    axes = Axes()
    model = Images("ccd", axes=axes)
    assert model.figure is None
    figure = Figure((axes,), title="")
    assert model.figure is figure
    view = FigureView(model.figure)
    view.close()
