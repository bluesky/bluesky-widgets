import tempfile

import numpy as np
from bluesky import RunEngine
from bluesky.plans import count, grid_scan, scan
from databroker._drivers.msgpack import BlueskyMsgpackCatalog
from ophyd.sim import SynSignal, det, det4, motor, motor1, motor2
from suitcase.msgpack import Serializer

random_img = SynSignal(func=lambda: np.random.random((5, 10, 10)), name="random_img")


def get_catalog():
    RE = RunEngine()

    directory = tempfile.TemporaryDirectory().name
    for i in range(1, 5):
        with Serializer(directory) as serializer:
            RE(scan([det], motor, -1, 1, 5 * i), serializer)
    with Serializer(directory) as serializer:
        RE(count([random_img], 3), serializer)
    with Serializer(directory) as serializer:
        RE(grid_scan([det4], motor1, -1, 2, 5, motor2, -1, 2, 7), serializer)

    catalog = BlueskyMsgpackCatalog(f"{directory}/*.msgpack")
    return catalog
