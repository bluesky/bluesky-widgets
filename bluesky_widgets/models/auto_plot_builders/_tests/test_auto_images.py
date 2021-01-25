from bluesky_live.run_builder import build_simple_run
import numpy

from .. import AutoImages
from ....headless.figures import HeadlessFigures


def test_images():
    "Test AutoImages with a 2D array."
    run = build_simple_run({"ccd": numpy.random.random((11, 13))})
    model = AutoImages()
    view = HeadlessFigures(model.figures)
    assert not model.figures
    model.add_run(run)
    assert len(model.figures) == 1
    assert model.figures[0].axes[0].artists
    view.close()


def test_images_multiple_fields():
    "Test AutoImages with multiple fields with varied shapes."
    run = build_simple_run(
        {
            "ccd": numpy.random.random((11, 13)),
            "ccd2": numpy.random.random((17, 19, 23)),
        }
    )
    model = AutoImages()
    view = HeadlessFigures(model.figures)
    assert not model.figures
    model.add_run(run)
    assert len(model.figures) == 2
    assert model.figures[0].axes[0].artists
    assert model.figures[1].axes[0].artists
    view.close()
