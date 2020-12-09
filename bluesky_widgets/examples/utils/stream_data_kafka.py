"""
Run like:

python -m bluesky_widgets.examples.utils.stream_data_kafka

It will publish Bluesky documents to kafka running on localhost:9092
until stopped.
"""
import asyncio
import logging
from functools import partial

import msgpack
import msgpack_numpy as mpn

from bluesky import RunEngine
from bluesky_kafka import Publisher
from bluesky.plans import scan
from bluesky.plan_stubs import sleep
from ophyd.sim import motor, det

log = logging.getLogger(__name__)


def stream_example_data(quiet=False):

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
        serializer=partial(msgpack.dumps, default=mpn.encode),
    )

    motor.delay = 0.22
    det.kind = "hinted"

    def infinite_plan():
        while True:
            for i in range(1, 5):
                yield from sleep(2)
                yield from scan([det], motor, -1, 1, 5 * i)

    RE = RunEngine(loop=asyncio.new_event_loop())
    RE.subscribe(kafka_publisher)

    # Just as a convenience, avoid collission with scan_ids of runs in Catalog.
    RE.md["scan_id"] = 100

    try:
        RE(infinite_plan())
    finally:
        RE.halt()


if __name__ == "__main__":
    import sys

    quiet = (len(sys.argv) > 1) and (sys.argv[1] in ("--quiet", "-q"))

    handler = logging.StreamHandler()
    handler.setLevel("INFO")
    log.setLevel("DEBUG")
    log.addHandler(handler)
    stream_example_data(quiet)

    # clear kafka topic?
