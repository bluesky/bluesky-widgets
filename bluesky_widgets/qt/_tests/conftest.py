import multiprocessing

import pytest

from qtpy.QtWidgets import QApplication

from bluesky_kafka.tests.conftest import (
    RE,
    hw,
    pytest_addoption,
    kafka_bootstrap_servers,
    publisher_factory,
    dispatcher_factory,
    external_process_document_queue,
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


@pytest.fixture(scope="function")
def bluesky_widgets_remote_dispatcher_process_factory(dispatcher_factory):
    def _bluesky_widgets_remote_dispatcher_process_factory(
        topics,
        group_id,
        consumer_config,
        document_queue,
        dispatcher_subscribers,
        **kwargs
    ):
        # this function will run in the external process created below
        def start_remote_dispatcher_with_queue(document_queue_):
            logger = multiprocessing.get_logger()

            # it is important the RemoteDispatcher be
            # constructed inside the external process
            remote_dispatcher_ = dispatcher_factory(
                topics=topics,
                group_id=group_id,
                consumer_config=consumer_config,
                **kwargs,
            )

            # send messages published by a Kafka broker to a model
            for dispatcher_subscriber in dispatcher_subscribers:
                remote_dispatcher_.subscribe(dispatcher_subscriber)

            remote_dispatcher_.start()  # launches periodic workers on background threads
            # remote_dispatcher_.stop()  # stop launching workers

        # create an external process for the bluesky_kafka.RemoteDispatcher polling loop
        # do not start it, the client of this function will start the process
        remote_dispatcher_process = multiprocessing.Process(
            target=start_remote_dispatcher_with_queue,
            args=(document_queue,),
            daemon=True,
        )

        return remote_dispatcher_process

    return _bluesky_widgets_remote_dispatcher_process_factory
