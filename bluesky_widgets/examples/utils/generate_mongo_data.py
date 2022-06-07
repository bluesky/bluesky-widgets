from bluesky import RunEngine
from bluesky.plans import count, scan
from databroker.mongo_normalized import MongoAdapter
from ophyd.sim import det, motor, SynSignal
from tiled.client import from_tree
import numpy as np
import uuid


random_img = SynSignal(func=lambda: np.random.random((5, 10, 10)), name="random_img")


def get_catalog():

    RE = RunEngine()

    uri = f"mongodb://localhost:27017/databroker-test-{uuid.uuid4()}"
    adapter = MongoAdapter.from_uri(uri)
    client = from_tree(adapter)
    for i in range(1, 5):
        RE(scan([det], motor, -1, 1, 5 * i), client.v1.insert)
    RE(count([random_img], 3), client.v1.insert)

    return client
