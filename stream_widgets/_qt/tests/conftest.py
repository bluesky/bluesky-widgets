import pytest

from qtpy.QtWidgets import QApplication

from ...examples.qt_bec import Viewer


@pytest.fixture
def qtbot(qtbot):
    """A modified qtbot fixture that makes sure no widgets have been leaked."""
    # Adapted from napari
    initial = QApplication.topLevelWidgets()
    yield qtbot
    QApplication.processEvents()
    leaks = set(QApplication.topLevelWidgets()).difference(initial)
    if leaks:
        raise AssertionError(f'Widgets leaked!: {leaks}')


@pytest.fixture(scope="function")
def make_test_viewer(qtbot, request):
    viewers = []

    def actual_factory(*model_args, **model_kwargs):
        model_kwargs['show'] = model_kwargs.pop(
            'show', request.config.getoption("--show-viewer")
        )
        viewer = Viewer(*model_args, **model_kwargs)
        viewers.append(viewer)
        return viewer

    yield actual_factory

    for viewer in viewers:
        viewer.close()
