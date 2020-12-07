"""
Run like:

python -m bluesky_widgets.examples.headless_figures

and it will print to stdout the names of the figures that it creates, one per line
"""
import tempfile

from bluesky import RunEngine
from bluesky.plans import scan
from ophyd.sim import motor, det

from bluesky_widgets.utils.streaming import stream_documents_into_runs
from bluesky_widgets.models.plot_builders import AutoRecentLines
from bluesky_widgets.headless.figures import HeadlessFigures
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog

model = AutoRecentLines(3)
view = HeadlessFigures(model.figures)

RE = RunEngine()
RE.subscribe(stream_documents_into_runs(model.add_run))


catalog = get_catalog()
scans = catalog.search({"plan_name": "scan"})
model.add_run(scans[-1], pinned=True)


def plan():
    for i in range(1, 5):
        yield from scan([det], motor, -1, 1, 1 + 2 * i)


RE(plan())


directory = tempfile.mkdtemp()
filenames = view.export_all(directory)
print("\n".join(f'"{filename}"' for filename in filenames))


from functools import partial
import os

import msgpack
import msgpack_numpy as mpn

from bluesky_kafka import BlueskyConsumer

bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
if bootstrap_servers is None:
    raise AttributeError("Environment variable KAFKA_BOOTSTRAP_SERVERS"
                         "must be set.")

kafka_deserializer = partial(msgpack.loads, object_hook=mpn.decode)
auto_offset_reset = "latest"
topics = ["^.*bluesky.documents"]

# Create a MongoConsumer that will automatically listen to new beamline topics.
# The parameter metadata.max.age.ms determines how often the consumer will check for
# new topics. The default value is 5000ms.
bluesky_consumer = BlueConsumer(
    topics=topics,
    bootstrap_servers=bootstrap_servers,
    group_id="kafka-unit-test-group-id",
    mongo_uri=mongo_uri,
    consumer_config={"auto.offset.reset": auto_offset_reset},
    polling_duration=1.0,
    deserializer=kafka_deserializer,
)

bluesky_consumer.start()
