"""
In one terminal start a RunEngine worker, which we will send commands to.

PROFILE_DIR=$(python -c "import bluesky_queueserver; import pathlib; print(pathlib.Path(bluesky_queueserver.__file__).parent)")
Start-re-manager \
    --startup-dir $PROFILE_DIR/profile_collection_sim/ \
    --zmq-data-proxy-addr localhost:5577

In another, start a message bus that will forward us Bluesky documents.

bluesky-0MQ-proxy -v 5577 5578

Finally, start this example module, connecting to both of those.

python -m bluesky_widgets.examples.advanced.qt_with_RE_worker tcp://localhost:60615 localhost:5578
"""  # noqa E501

from bluesky_widgets.utils.streaming import stream_documents_into_runs
from bluesky_widgets.qt.zmq_dispatcher import RemoteDispatcher
from bluesky_widgets.models.plot_builders import Lines
from bluesky_widgets.qt.figures import QtFigure
from bluesky_widgets.qt import gui_qt
from bluesky_queueserver.manager.comms import ZMQCommSendThreads
import sys


def main():
    with gui_qt("Example App"):
        worker_address, message_bus_address = sys.argv[1:]
        dispatcher = RemoteDispatcher(message_bus_address)
        client = ZMQCommSendThreads(zmq_server_address=worker_address)
        client.send_message(method="environment_open")
        client.send_message(
            method="queue_item_add",
            params={
                "plan": {"name": "scan", "args": [["det"], "motor", -5, 5, 11]},
                "user": "",
                "user_group": "admin",
            },
        )
        model = Lines("motor", ["det"], max_runs=3)
        dispatcher.subscribe(stream_documents_into_runs(model.add_run))
        view = QtFigure(model.figure)
        view.show()
        dispatcher.start()
        client.send_message(method="queue_start")


if __name__ == "__main__":
    main()
