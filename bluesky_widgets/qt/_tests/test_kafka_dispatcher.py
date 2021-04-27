import logging
import time

from bluesky import RunEngine
from bluesky.plans import count

from bluesky_widgets.models.plot_builders import Lines
from bluesky_widgets.utils.streaming import stream_documents_into_runs

from bluesky_widgets.qt.kafka_dispatcher import QtRemoteDispatcher


test_logger = logging.getLogger("bluesky_widgets.qt.tests")


def test_publisher_and_qt_remote_dispatcher(
    kafka_bootstrap_servers, temporary_topics, publisher_factory, qapp, hw
):
    """Test publishing and dispatching bluesky documents in Kafka messages.
    Messages will be "dispatched" by a `bluesky_kafka.RemoteDispatcher`.
    Parameters
    ----------
    kafka_bootstrap_servers: str (pytest fixture)
        comma-delimited string of Kafka broker host:port, for example "localhost:9092"
    temporary_topics: context manager (pytest fixture)
        creates and cleans up temporary Kafka topics for testing
    publisher_factory: pytest fixture
        fixture-as-a-factory for creating Publishers
    qapp: pytest-qt fixture
        needed to force processing of Qt events
    hw: pytest fixture
        ophyd simulated hardware objects
    """

    with temporary_topics(topics=["test.qt.remote.dispatcher"]) as (topic,):

        bluesky_publisher = publisher_factory(
            topic=topic,
            key=f"{topic}.key",
            flush_on_stop_doc=True,
        )

        # trying to test _waiting_for_start
        bluesky_publisher("descriptor", {})
        bluesky_publisher("event", {})
        # bluesky_publisher("stop", {})

        published_bluesky_documents = []

        # this function will store all documents
        # published by the RunEngine in a list
        def store_published_document(name, document):
            published_bluesky_documents.append((name, document))

        RE = RunEngine()
        RE.subscribe(bluesky_publisher)
        RE.subscribe(store_published_document)

        RE(count([hw.det]))

        # it is assumed that RE(count()) will produce four
        # documents: start, descriptor, event, stop
        assert len(published_bluesky_documents) == 4

        lines_model = Lines(x="time", ys=["det"])
        assert len(lines_model.runs) == 0

        qt_remote_dispatcher = QtRemoteDispatcher(
            topics=[topic],
            bootstrap_servers=kafka_bootstrap_servers,
            group_id=f"{topic}.consumer.group",
            consumer_config={
                # this consumer is intended to read messages that
                # were published before it starts, so it is necessary
                # to specify "earliest" here
                "auto.offset.reset": "earliest",
            },
            polling_duration=1.0,
        )

        qt_remote_dispatcher.subscribe(stream_documents_into_runs(lines_model.add_run))

        dispatched_bluesky_documents = []

        # the QtRemoteDispatcher will use this function
        # to build a list of documents delivered by Kafka
        def store_dispatched_document(name, document):
            test_logger.debug("store_dispatched_document name='%s'", name)
            dispatched_bluesky_documents.append((name, document))

        qt_remote_dispatcher.subscribe(store_dispatched_document)

        # this function will be given to QtRemoteDispatcher.start()
        # it returns False to end the polling loop
        # as soon as it sees one stop document
        def until_first_stop_document():
            dispatched_bluesky_document_names = [name for name, _ in dispatched_bluesky_documents]
            test_logger.debug("until_first_stop_document %s", dispatched_bluesky_document_names)
            if "stop" in dispatched_bluesky_document_names:
                return False
            else:
                return True

        # start() will return when 'until_first_stop_document' returns False
        qt_remote_dispatcher.start(
            continue_polling=until_first_stop_document,
        )

        while len(dispatched_bluesky_documents) < 3:
            # waiting for all Kafka messages to land
            test_logger.debug("processing Qt Events")
            qapp.processEvents()

            time.sleep(1.0)
            test_logger.debug(
                "waiting for all Kafka messages, %d so far",
                len(dispatched_bluesky_documents),
            )

        assert len(published_bluesky_documents) == len(dispatched_bluesky_documents)

        assert len(lines_model.runs) == 1
