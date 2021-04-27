import asyncio
import logging
from multiprocessing import Process, Queue
from pathlib import Path
import tempfile

from bluesky.callbacks.zmq import Publisher
from bluesky.callbacks import LiveTable
from bluesky.preprocessors import SupplementalData
from suitcase.jsonl import Serializer
from bluesky import RunEngine
from ophyd.sim import det, motor, motor1, motor2
from bluesky.plans import scan
from event_model import RunRouter
from bluesky.plan_stubs import sleep


log = logging.getLogger(__name__)


def run_proxy(queue):
    """
    Run Proxy on random, free ports and communicate the port numbers back.
    """
    from bluesky.callbacks.zmq import Proxy

    proxy = Proxy()
    queue.put((proxy.in_port, proxy.out_port))
    proxy.start()


def run_publisher(in_port, data_path, quiet=False):
    """
    Acquire data in an infinite loop and publish it.
    """
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
    if not quiet:
        RE.subscribe(LiveTable(["motor", "det"]))

    motor.delay = 0.2
    det.kind = "hinted"

    def infinite_plan():
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


def stream_example_data(data_path, quiet=False):
    data_path = Path(data_path)
    log.info(
        f"Writing example data into directory {data_path!s}. It will be deleted when this process is stopped."
    )

    queue = Queue()
    proxy_process = Process(target=run_proxy, args=(queue,))
    proxy_process.start()
    in_port, out_port = queue.get()
    log.info(f"Connect a consumer to localhost:{out_port}")

    publisher_process = Process(target=run_publisher, args=(in_port, data_path, quiet))
    publisher_process.start()
    log.info("Demo acquisition has started.")

    return f"localhost:{out_port}", proxy_process, publisher_process


if __name__ == "__main__":
    import logging
    import sys

    quiet = (len(sys.argv) > 1) and (sys.argv[1] in ("--quiet", "-q"))

    handler = logging.StreamHandler()
    handler.setLevel("INFO")
    log.setLevel("DEBUG")
    log.addHandler(handler)
    with tempfile.TemporaryDirectory() as directory:
        stream_example_data(directory, quiet)
    # Delete example data at exit.
