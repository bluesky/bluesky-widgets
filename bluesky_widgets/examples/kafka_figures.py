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

from bluesky_widgets.utils.streaming import stream_documents_into_runs
from bluesky_widgets.models.plot_builders import AutoRecentLines
from bluesky_widgets.headless.figures import HeadlessFigures
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog

class ThumbnailGenerator:
    def __init__(self):
        self.model = AutoRecentLines(3)
        self.view = HeadlessFigures(model.figures)

    def __call__(self, topic, name, doc):

    def finish_run(self):
        stream_documents_into_runs(self.model.add_run))
        directory = tempfile.mkdtemp()
        filenames = view.export_all(directory)
        print("\n".join(f'"{filename}"' for filename in filenames))

thumbnail_generator = ThumbnailGenerator()

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
                process_document=thumbnail_generator,
            )

bluesky_consumer.start()
