import time

from bluesky_live.list import ListModel
from bluesky_live.event import EmitterGroup, Event
from bluesky_queueserver.manager.comms import ZMQCommSendThreads


class PlanItem:
    def __init__(self, name, args):
        self._name = name
        self._args = args
        self.events = EmitterGroup(
            source=self,
            name=Event,
        )

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if value == self._name:
            return
        self._name = value
        self.events.name(name=value)

    @property
    def args(self):
        return self._args

    @args.setter
    def args(self, value):
        # TODO Deal with *mutation* (editing) of the args the same way we deal
        # with mutation of plot styles.
        if value == self._args:
            return
        self._args = value
        self.events.args(args=value)


class PlanQueue(ListModel):
    pass


class PlanHistory(ListModel):
    pass


class BigModel:
    def __init__(self):
        self._client = RunEngineClient()
        self.plan_queue = PlanQueue()
        self.plan_queue.events.adding.connect(self._on_plan_added)
        self.plan_history = PlanHistory()

    def _on_plan_added(self, event):
        plan_item = event.item
        self._client.add(plan_item.name, plan_item.args)


class RunEngineClient:
    def __init__(self, worker_address):
        self._client = ZMQCommSendThreads(zmq_server_address=worker_address)

    def clear(self):
        # Clear the queue.
        response = self._client.send_message(method="queue_clear")
        if not response["success"]:
            raise RuntimeError(f"Failed to clear the plan queue: {response['msg']}")

    def environment_open(self, timeout=0):
        """
        Open RE Worker environment. Blocks until operation is complete or timeout expires.
        If ``timeout=0``, then the function blocks until operation is complete.

        Parameters
        ----------
        timeout : float
            maximum time for the operation. Exception is raised if timeout expires.
            If ``timeout=0``, the function blocks until operation is complete.

        Returns
        -------
        None
        """
        # Check if RE Worker environment already exists and RE manager is idle.
        status = self._client.send_message(method="status")
        if status["manager_state"] != "idle":
            raise RuntimeError(
                f"RE Manager state must be 'idle': current state: {status['manager_state']}"
            )
        if status["worker_environment_exists"]:
            raise RuntimeError("RE Worker environment already exists")

        # Initiate opening of RE Worker environment
        response = self._client.send_message(method="environment_open")
        if not response["success"]:
            raise RuntimeError(
                f"Failed to open RE Worker environment: {response['msg']}"
            )

        # Wait for the environment to be created.
        if timeout:
            t_stop = time.time() + timeout
        while True:
            status2 = self._client.send_message(method="status")
            if (
                status2["worker_environment_exists"]
                and status2["manager_state"] == "idle"
            ):
                break
            if timeout and (time.time() > t_stop):
                raise RuntimeError("Failed to start RE Worker: timeout occurred")
            time.sleep(0.5)

    def environment_close(self, timeout=0):
        """
        Close RE Worker environment. Blocks until operation is complete or timeout expires.
        If ``timeout=0``, then the function blocks until operation is complete.

        Parameters
        ----------
        timeout : float
            maximum time for the operation. Exception is raised if timeout expires.
            If ``timeout=0``, the function blocks until operation is complete.

        Returns
        -------
        None
        """
        # Check if RE Worker environment already exists and RE manager is idle.
        status = self._client.send_message(method="status")
        if status["manager_state"] != "idle":
            raise RuntimeError(
                f"RE Manager state must be 'idle': current state: {status['manager_state']}"
            )
        if not status["worker_environment_exists"]:
            raise RuntimeError("RE Worker environment does not exist")

        # Initiate opening of RE Worker environment
        response = self._client.send_message(method="environment_close")
        if not response["success"]:
            raise RuntimeError(
                f"Failed to close RE Worker environment: {response['msg']}"
            )

        # Wait for the environment to be created.
        if timeout:
            t_stop = time.time() + timeout
        while True:
            status2 = self._client.send_message(method="status")
            if (
                not status2["worker_environment_exists"]
                and status2["manager_state"] == "idle"
            ):
                break
            if timeout and (time.time() > t_stop):
                raise RuntimeError("Failed to start RE Worker: timeout occurred")
            time.sleep(0.5)

    def environment_destroy(self, timeout=0):
        """
        Destroy (unresponsive) RE Worker environment. The function is intended for the cases when
        the environment is unresponsive and can not be stopped using ``environment_close``.
        Blocks until operation is complete or timeout expires. If ``timeout=0``, then the function
        blocks until operation is complete.

        Parameters
        ----------
        timeout : float
            maximum time for the operation. Exception is raised if timeout expires.
            If ``timeout=0``, the function blocks until operation is complete.

        Returns
        -------
        None
        """
        # Check if RE Worker environment already exists and RE manager is idle.
        status = self._client.send_message(method="status")
        if not status["worker_environment_exists"]:
            raise RuntimeError("RE Worker environment does not exist")

        # Initiate opening of RE Worker environment
        response = self._client.send_message(method="environment_destroy")
        if not response["success"]:
            raise RuntimeError(
                f"Failed to destroy RE Worker environment: {response['msg']}"
            )

        # Wait for the environment to be created.
        if timeout:
            t_stop = time.time() + timeout
        while True:
            status2 = self._client.send_message(method="status")
            if (
                not status2["worker_environment_exists"]
                and status2["manager_state"] == "idle"
            ):
                break
            if timeout and (time.time() > t_stop):
                raise RuntimeError("Failed to start RE Worker: timeout occurred")
            time.sleep(0.5)

    def add(self, plan_name, plan_args):
        # Add plan to queue
        response = self._client.send_message(
            method="queue_item_add",
            params={
                "plan": {"name": plan_name, "args": plan_args},
                "user": "",
                "user_group": "admin",
            },
        )
        if not response["success"]:
            raise RuntimeError(f"Failed to add plan to the queue: {response['msg']}")
