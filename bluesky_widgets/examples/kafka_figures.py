"""
Run like:

python -m bluesky_widgets.examples.headless_figures

and it will print to stdout the names of the figures that it creates, one per line
"""
from functools import partial
import os

import msgpack
import msgpack_numpy as mpn
from bluesky_kafka import RemoteDispatcher

from bluesky_widgets.utils.streaming import stream_documents_into_runs
from bluesky_widgets.models.plot_builders import AutoRecentLines
from bluesky_widgets.headless.figures import HeadlessFigures
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
from bluesky_widgets.models.utils import run_is_live_and_not_completed

def export_thumbnails_when_complete(run):
    "Given a BlueskyRun, export thumbnail(s) to a directory when it completes."
    model = AutoRecentLines(3)
    model.add_run(run)
    view = HeadlessFigures(model.figures)

    directory = "the uid or something"

  # If the Run is already done by the time we got it, export now.
    # Otherwise, schedule it to export whenever it finishes.
    if run_is_live_and_not_completed(run):
        run.events.completed.connect(lambda event: view.export_all(directory))
    else:
        view.export_all(directory)


if __name__ == "__main__":
    bootstrap_servers = "127.0.0.1:9092"
    kafka_deserializer = partial(msgpack.loads, object_hook=mpn.decode)
    topics = ["widgets_test.bluesky.documents"]
    consumer_config = {
                    "auto.commit.interval.ms": 100,
                    "auto.offset.reset": "latest"
                }

    dispatcher = RemoteDispatcher(
                    topics=topics,
                    bootstrap_servers=kafka_bootstrap_servers,
                    group_id="widgets_test",
                    consumer_config=consumer_config,
                )

    dispatcher.subscribe(dispatcher.subscribe(export_thumbnails_when_complete))
    dispatcher.start()
