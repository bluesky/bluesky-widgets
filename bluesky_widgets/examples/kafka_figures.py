"""
Run like:

python -m bluesky_widgets.examples.headless_figures

and it will print to stdout the names of the figures that it creates, one per line
"""
from functools import partial
import os

import msgpack
import msgpack_numpy as mpn

from bluesky_kafka import BlueskyConsumer

bootstrap_servers = "127.0.0.1:9092"
kafka_deserializer = partial(msgpack.loads, object_hook=mpn.decode)
auto_offset_reset = "latest"
topics = ["widgets_test.bluesky.documents"]

consumer_config = {
                "auto.commit.interval.ms": 100,
            }

 bluesky_consumer = BlueskyConsumer(
                topics=topics,
                bootstrap_servers=kafka_bootstrap_servers,
                group_id="widgets_test",
                consumer_config=consumer_config,
                process_document=put_document_in_queue,
            )

bluesky_consumer.start()
