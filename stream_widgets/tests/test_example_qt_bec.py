import pytest
from ..examples.qt_bec import Viewer


@pytest.fixture(scope="function")
def make_test_viewer(qtbot, request):
    viewers = []

    def actual_factory(*model_args, **model_kwargs):
        # TODO Trick copied from napari, to implement later
        # model_kwargs['show'] = model_kwargs.pop(
        #     'show', request.config.getoption("--show-viewer")
        # )
        viewer = Viewer(*model_args, **model_kwargs)
        viewers.append(viewer)
        return viewer

    yield actual_factory

    for viewer in viewers:
        viewer.close()


def test_viewer(make_test_viewer):
    viewer = make_test_viewer()
    assert viewer.search_input.since is None
