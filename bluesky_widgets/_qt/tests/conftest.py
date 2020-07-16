import pytest

from qtpy.QtWidgets import QApplication


@pytest.fixture
def qtbot(qtbot):
    """A modified qtbot fixture that makes sure no widgets have been leaked."""
    # Adapted from napari
    initial = QApplication.topLevelWidgets()
    yield qtbot
    QApplication.processEvents()
    leaks = set(QApplication.topLevelWidgets()).difference(initial)
    if leaks:
        raise AssertionError(f"Widgets leaked!: {leaks}")
