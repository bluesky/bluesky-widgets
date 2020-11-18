import logging
from multiprocessing import Process, Queue
from pathlib import Path
import tempfile

from suitcase.jsonl import Serializer
from bluesky import RunEngine
from ophyd.sim import det, det4, noisy_det, motor, motor1, motor2, img
from bluesky.plans import scan, count, grid_scan
from bluesky.preprocessors import SupplementalData
from event_model import RunRouter
from ophyd.sim import SynSignal
import numpy as np

det.kind = "hinted"
noisy_det.kind = "hinted"
det4.kind = "hinted"


log = logging.getLogger(__name__)

random_img = SynSignal(func=lambda: np.random.random((5, 10, 10)), name="random_img")


def generate_example_catalog(data_path):
    data_path = Path(data_path)

    def factory(name, doc):
        serializer = Serializer(data_path / "abc")
        serializer("start", doc)
        return [serializer], []

    RE = RunEngine()
    sd = SupplementalData()
    RE.preprocessors.append(sd)
    sd.baseline.extend([motor1, motor2])
    rr = RunRouter([factory])
    RE.subscribe(rr)
    RE(count([det]))
    RE(count([noisy_det], 5))
    RE(scan([det], motor, -1, 1, 7))
    RE(grid_scan([det4], motor1, -1, 1, 4, motor2, -1, 1, 7, False))
    RE(scan([det], motor, -1, 1, motor2, -1, 1, 5))
    RE(count([noisy_det, det], 5))
    RE(count([random_img], 5))
    RE(count([img], 5))

    def factory(name, doc):
        serializer = Serializer(data_path / "xyz")
        serializer("start", doc)
        return [serializer], []

    RE = RunEngine()
    rr = RunRouter([factory])
    RE.subscribe(rr)
    RE(count([det], 3))

    catalog_filepath = data_path / "catalog.yml"
    with open(catalog_filepath, "w") as file:
        file.write(
            f"""
sources:
  abc:
    description: Some imaginary beamline
    driver: bluesky-jsonl-catalog
    container: catalog
    args:
      paths: {Path(data_path) / 'abc' / '*.jsonl'}
      handler_registry:
        NPY_SEQ: ophyd.sim.NumpySeqHandler
    metadata:
      beamline: "00-ID"
  xyz:
    description: Some imaginary beamline
    driver: bluesky-jsonl-catalog
    container: catalog
    args:
      paths: {Path(data_path) / 'xyz' / '*.jsonl'}
      handler_registry:
        NPY_SEQ: ophyd.sim.NumpySeqHandler
    metadata:
      beamline: "99-ID"
"""
        )
    return str(catalog_filepath)


def run_proxy(queue):
    """
    Run Proxy on random, free ports and communicate the port numbers back.
    """
    from bluesky.callbacks.zmq import Proxy

    proxy = Proxy()
    queue.put((proxy.in_port, proxy.out_port))
    proxy.start()


def run_publisher(in_port, data_path):
    """
    Acquire data in an infinite loop and publish it.
    """
    import asyncio
    from bluesky.callbacks.zmq import Publisher
    from bluesky.callbacks import LiveTable
    from suitcase.jsonl import Serializer
    from ophyd.sim import noisy_det, motor1, motor2
    from bluesky.plans import count
    from bluesky.preprocessors import SupplementalData
    from bluesky.plan_stubs import sleep

    publisher = Publisher(f"localhost:{in_port}")
    RE = RunEngine(loop=asyncio.new_event_loop())
    sd = SupplementalData()
    RE.preprocessors.append(sd)
    sd.baseline.extend([motor1, motor2])
    RE.subscribe(publisher)

    def factory(name, doc):
        serializer = Serializer(data_path / "abc", flush=True)
        return [serializer], []

    rr = RunRouter([factory])
    RE.subscribe(rr)
    RE.subscribe(LiveTable(["motor", "det"]))

    def infinite_plan():
        motor.delay = 0.2
        while True:
            for i in range(1, 5):
                yield from sleep(2)
                yield from scan([det], motor, -1, 1, 5 * i)

    # Just as a convenience, avoid collission with scan_ids of runs in Catalog.
    RE.md["scan_id"] = 100
    try:
        RE(infinite_plan())
    finally:
        RE.halt()


def stream_example_data(data_path):
    data_path = Path(data_path)
    log.info(
        f"Writing example data into directory {data_path!s}. "
        "It will be deleted when this process is stopped."
    )

    queue = Queue()
    proxy_process = Process(target=run_proxy, args=(queue,))
    proxy_process.start()
    in_port, out_port = queue.get()
    log.info(f"Connect a consumer to localhost:{out_port}")

    publisher_process = Process(target=run_publisher, args=(in_port, data_path))
    publisher_process.start()
    log.info("Demo acquisition has started.")

    return f"localhost:{out_port}", proxy_process, publisher_process


if __name__ == "__main__":
    import logging

    handler = logging.StreamHandler()
    handler.setLevel("INFO")
    log.setLevel("DEBUG")
    log.addHandler(handler)
    with tempfile.TemporaryDirectory() as directory:
        stream_example_data(directory)
    # Delete example data at exit.
