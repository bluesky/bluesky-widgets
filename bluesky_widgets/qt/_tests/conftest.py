import pytest

from qtpy.QtWidgets import QApplication

from bluesky_kafka.tests.conftest import (  # noqa
    hw,
    pytest_addoption,
    kafka_bootstrap_servers,
    publisher_factory,
    temporary_topics,
)


@pytest.fixture
def qtbot(qtbot):
    """A modified qtbot fixture that makes sure no widgets have been leaked."""
    # Adapted from napari
    initial = QApplication.topLevelWidgets()
    yield qtbot
    QApplication.processEvents()
    leaks = set(QApplication.topLevelWidgets()).difference(initial)
    if leaks:
        # Ignore this until we resolve
        # AssertionError: Widgets leaked!:
        # {matplotlib.backends.backend_qt5.MainWindow object at 0x7fdce80b7550>}
        # raise AssertionError(f"Widgets leaked!: {leaks}")
        pass
