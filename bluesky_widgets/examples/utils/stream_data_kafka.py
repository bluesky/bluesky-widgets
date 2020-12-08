"""
Run like:

python -m bluesky_widgets.examples.publish_run_to_kafka

It will publish a run to kafka running on localhost:9092
"""
from bluesky import RunEngine
from bluesky_kafka import Publisher
from bluesky.plans import scan
from ophyd.sim import motor, det

bootstrap_servers = "127.0.0.1:9092"

producer_config = {
                "acks": 1,
                "enable.idempotence": False,
                "request.timeout.ms": 1000,
            }

kafka_publisher = Publisher(
            topic="widgets_test.bluesky.documents",
            key="widgets_test",
            bootstrap_servers=bootstrap_servers,
            producer_config=producer_config,
        )

RE = RunEngine()
RE.subscribe(kafka_publisher)


def plan():
    for i in range(1, 5):
        yield from scan([det], motor, -1, 1, 1 + 2 * i)


RE(plan())
