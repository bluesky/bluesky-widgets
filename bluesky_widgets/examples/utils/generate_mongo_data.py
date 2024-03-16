# Based on databroker/examples/generate_mongo_data.py
import uuid

import numpy as np
from bluesky import RunEngine
from bluesky.plans import count, scan
from databroker._drivers.mongo_normalized import BlueskyMongoCatalog
from ophyd.sim import SynSignal, det, motor
from suitcase.mongo_normalized import Serializer

random_img = SynSignal(func=lambda: np.random.random((5, 10, 10)), name="random_img")


def get_catalog():
    RE = RunEngine()

    mds = f"mongodb://localhost:27017/databroker-test-{uuid.uuid4()}"
    fs = f"mongodb://localhost:27017/databroker-test-{uuid.uuid4()}"
    serializer = Serializer(mds, fs)
    for i in range(1, 5):
        RE(scan([det], motor, -1, 1, 5 * i), serializer)
    RE(count([random_img], 3), serializer)

    catalog = BlueskyMongoCatalog(mds, fs)
    return catalog
