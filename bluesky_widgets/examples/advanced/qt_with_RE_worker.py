"""
In one terminal start a RunEngine worker, which we will send commands to.

start-re-manager --zmq-data-proxy-addr localhost:5577

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
import time


def main():
    with gui_qt("Example App"):
        worker_address, message_bus_address = sys.argv[1:]
        dispatcher = RemoteDispatcher(message_bus_address)
        client = ZMQCommSendThreads(zmq_server_address=worker_address)

        # NOTE: this example starts only if RE Manager is idle and the queue is cleared.
        #   Those are optional steps that ensure that the code in this example is executed correctly.

        # Check if RE Worker environment already exists and RE manager is idle.
        status = client.send_message(method="status")
        if status["manager_state"] != "idle":
            raise RuntimeError(f"RE Manager state must be 'idle': current state: {status['manager_state']}")

        # Clear the queue.
        response = client.send_message(method="queue_clear")
        if not response["success"]:
            raise RuntimeError(f"Failed to clear the plan queue: {response['msg']}")

        # Open the new environment only if it does not exist.
        if not status["worker_environment_exists"]:
            # Initiate opening of RE Worker environment
            response = client.send_message(method="environment_open")
            if not response["success"]:
                raise RuntimeError(f"Failed to open RE Worker environment: {response['msg']}")

            # Wait for the environment to be created.
            t_timeout = 10
            t_stop = time.time() + t_timeout
            while True:
                status2 = client.send_message(method="status")
                if status2["worker_environment_exists"] and status2["manager_state"] == "idle":
                    break
                if time.time() > t_stop:
                    raise RuntimeError("Failed to start RE Worker: timeout occurred")
                time.sleep(0.5)

        # Add plan to queue
        response = client.send_message(
            method="queue_item_add",
            params={
                "item": {
                    "item_type": "plan",
                    "name": "scan",
                    "args": [["det"], "motor", -5, 5, 11],
                },
                "user": "Bluesky Widgets",  # Name of the user submitting item to the queue
                "user_group": "admin",
            },
        )
        if not response["success"]:
            raise RuntimeError(f"Failed to add plan to the queue: {response['msg']}")

        model = Lines("motor", ["det"], max_runs=3)
        dispatcher.subscribe(stream_documents_into_runs(model.add_run))
        view = QtFigure(model.figure)
        view.show()
        dispatcher.start()

        response = client.send_message(method="queue_start")
        if not response["success"]:
            raise RuntimeError(f"Failed to start the queue: {response['msg']}")


if __name__ == "__main__":
    main()
