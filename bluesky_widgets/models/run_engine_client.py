import time

from bluesky_live.event import EmitterGroup, Event
from bluesky_queueserver.manager.comms import ZMQCommSendThreads, CommTimeoutError


# class PlanItem:
#     def __init__(self, name, args):
#         self._name = name
#         self._args = args
#         self.events = EmitterGroup(
#             source=self,
#             name=Event,
#         )
#
#     @property
#     def name(self):
#         return self._name
#
#     @name.setter
#     def name(self, value):
#         if value == self._name:
#             return
#         self._name = value
#         self.events.name(name=value)
#
#     @property
#     def args(self):
#         return self._args
#
#     @args.setter
#     def args(self, value):
#         # TODO Deal with *mutation* (editing) of the args the same way we deal
#         # with mutation of plot styles.
#         if value == self._args:
#             return
#         self._args = value
#         self.events.args(args=value)
#
#
# class PlanQueue(ListModel):
#     pass
#
#
# class PlanHistory(ListModel):
#     pass


class RunEngineClient:
    def __init__(self, worker_address=None):
        self._client = ZMQCommSendThreads(zmq_server_address=worker_address)

        # User name and group are hard coded for now
        self._user_name = "GUI Client"
        self._user_group = "admin"

        self._re_manager_status = {}
        self._re_manager_connected = None
        self._re_manager_status_time = time.time()
        # Minimum period of status update (avoid excessive call frequency)
        self._re_manager_status_update_period = 0.2

        self._allowed_devices = {}
        self._allowed_plans = {}
        self._plan_queue_items = []
        self._running_item = {}
        self._plan_queue_uid = ""
        self._plan_history_items = []
        self._plan_history_uid = ""

        # UID of the selected queue item, "" if no items are selected
        self._selected_queue_item_uid = ""

        self.events = EmitterGroup(
            source=self,
            status_changed=Event,
            plan_queue_changed=Event,
            plan_history_changed=Event,
            allowed_devices_changed=Event,
            allowed_plans_changed=Event,
            queue_item_selection_changed=Event,
        )

    @property
    def re_manager_status(self):
        return self._re_manager_status

    @property
    def re_manager_accessible(self):
        return self._re_manager_connected

    def clear(self):
        # Clear the queue.
        response = self._client.send_message(method="queue_clear")
        if not response["success"]:
            raise RuntimeError(f"Failed to clear the plan queue: {response['msg']}")

    def clear_connection_status(self):
        """
        This function is not expected to clear 'status', only 'self._re_manager_connected'.
        """
        self._re_manager_connected = None
        self.events.status_changed(
            status=self._re_manager_status,
            is_connected=self._re_manager_connected,
        )

    def manager_connecting_ops(self):
        """
        Sequence of additional operations that should be performed while connecting to RE Manager.
        """
        self.load_allowed_devices()
        self.load_allowed_plans()
        self.load_plan_queue()
        self.load_plan_history()

    def load_re_manager_status(self, *, enforce=False):
        if enforce or (
            time.time() - self._re_manager_status_time
            > self._re_manager_status_update_period
        ):
            status = self._re_manager_status.copy()
            accessible = self._re_manager_connected
            try:
                new_manager_status = self._client.send_message(
                    method="status", raise_exceptions=True
                )
                self._re_manager_status.clear()
                self._re_manager_status.update(new_manager_status)
                self._re_manager_connected = True

                new_queue_uid = self._re_manager_status.get("plan_queue_uid", "")
                if new_queue_uid != self._plan_queue_uid:
                    self.load_plan_queue()
                new_history_uid = self._re_manager_status.get("plan_history_uid", "")
                if new_history_uid != self._plan_history_uid:
                    self.load_plan_history()

            except CommTimeoutError:
                self._re_manager_connected = False
            if (status != self._re_manager_status) or (
                accessible != self._re_manager_connected
            ):
                # Status changed. Initiate the updates
                self.events.status_changed(
                    status=self._re_manager_status,
                    is_connected=self._re_manager_connected,
                )

    def load_allowed_devices(self):
        try:
            result = self._client.send_message(
                method="devices_allowed", raise_exceptions=True
            )
            if result["success"] is False:
                raise RuntimeError(
                    f"Failed to load list of allowed devices: {result['msg']}"
                )
            self._allowed_devices.clear()
            self._allowed_devices.update(result["devices_allowed"])
            self.events.allowed_devices_changed(
                allowed_devices=self._allowed_devices,
            )
        except Exception as ex:
            print(f"Exception: {ex}")

    def load_allowed_plans(self):
        try:
            result = self._client.send_message(
                method="plans_allowed", raise_exceptions=True
            )
            if result["success"] is False:
                raise RuntimeError(
                    f"Failed to load list of allowed plans: {result['msg']}"
                )
            self._allowed_plans.clear()
            self._allowed_plans.update(result["plans_allowed"])
            self.events.allowed_plans_changed(
                allowed_plans=self._allowed_plans,
            )
        except Exception as ex:
            print(f"Exception: {ex}")

    def load_plan_queue(self):
        try:
            result = self._client.send_message(
                method="queue_get", raise_exceptions=True
            )
            if result["success"] is False:
                raise RuntimeError(f"Failed to load queue: {result['msg']}")
            self._plan_queue_items.clear()
            self._plan_queue_items.extend(result["items"])
            self._running_item.clear()
            self._running_item.update(result["running_item"])
            self._plan_queue_uid = result["plan_queue_uid"]
            self.events.plan_queue_changed(
                plan_queue_items=self._plan_queue_items,
                running_item=self._running_item,
            )

        except Exception as ex:
            print(f"Exception: {ex}")

    def load_plan_history(self):
        try:
            result = self._client.send_message(
                method="history_get", raise_exceptions=True
            )
            if result["success"] is False:
                raise RuntimeError(f"Failed to load history: {result['msg']}")
            self._plan_history_items.clear()
            self._plan_history_items.extend(result["items"])
            self._plan_history_uid = result["plan_history_uid"]
            self.events.plan_history_changed(
                plan_history_items=self._plan_history_items,
            )
        except Exception as ex:
            print(f"Exception: {ex}")

    @property
    def selected_queue_item_uid(self):
        return self._selected_queue_item_uid

    @selected_queue_item_uid.setter
    def selected_queue_item_uid(self, item_uid):
        if self._selected_queue_item_uid != item_uid:
            self._selected_queue_item_uid = item_uid
            self.events.queue_item_selection_changed(selected_item_uid=item_uid)

    def queue_item_uid_to_number(self, item_uid):
        for n, item in enumerate(self._plan_queue_items):
            if "item_uid" in item:
                if item["item_uid"] == item_uid:
                    return n
        return -1  # Item was not found

    # ============================================================================
    #                  Operations with RE Environment

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
        self.load_re_manager_status()
        status = self._re_manager_status
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
            self.load_re_manager_status()
            status2 = self._re_manager_status
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
        self.load_re_manager_status()
        status = self._re_manager_status
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
            self.load_re_manager_status()
            status2 = self._re_manager_status
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
        self.load_re_manager_status()
        status = self._re_manager_status
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
            self.load_re_manager_status()
            status2 = self._re_manager_status
            if (
                not status2["worker_environment_exists"]
                and status2["manager_state"] == "idle"
            ):
                break
            if timeout and (time.time() > t_stop):
                raise RuntimeError("Failed to start RE Worker: timeout occurred")
            time.sleep(0.5)

    # ============================================================================
    #                        Queue Control

    def queue_start(self):
        response = self._client.send_message(method="queue_start")
        if not response["success"]:
            raise RuntimeError(f"Failed to start the queue: {response['msg']}")

    def queue_stop(self):
        response = self._client.send_message(method="queue_stop")
        if not response["success"]:
            raise RuntimeError(
                f"Failed to request stopping the queue: {response['msg']}"
            )

    def queue_stop_cancel(self):
        response = self._client.send_message(method="queue_stop_cancel")
        if not response["success"]:
            raise RuntimeError(
                f"Failed to cancel request to stop the queue: {response['msg']}"
            )

    # ============================================================================
    #                        RE Control

    def _wait_for_completion(self, *, condition, msg="complete operation", timeout=0):
        if timeout:
            t_stop = time.time() + timeout

        while True:
            self.load_re_manager_status()
            status = self._re_manager_status
            if condition(status):
                break
            if timeout and (time.time() > t_stop):
                raise RuntimeError(f"Failed to {msg}: timeout occurred")
            time.sleep(0.5)

    def re_pause(self, timeout=0, *, option):
        """
        Pause execution of a plan.

        Parameters
        ----------
        timeout : float
            maximum time for the operation. Exception is raised if timeout expires.
            If ``timeout=0``, the function blocks until operation is complete.

        option : str
            "immediate" or "deferred"
        Returns
        -------
        None
        """

        # Initiate opening of RE Worker environment
        response = self._client.send_message(
            method="re_pause", params={"option": option}
        )
        if not response["success"]:
            raise RuntimeError(f"Failed to pause the running plan: {response['msg']}")

        def condition(status):
            return status["manager_state"] in ("idle", "paused")

        self._wait_for_completion(
            condition=condition, msg="pause the running plan", timeout=timeout
        )

    def re_resume(self, timeout=0):
        """
        Pause execution of a plan.

        Parameters
        ----------
        timeout : float
            maximum time for the operation. Exception is raised if timeout expires.
            If ``timeout=0``, the function blocks until operation is complete.

        Returns
        -------
        None
        """

        # Initiate opening of RE Worker environment
        response = self._client.send_message(method="re_resume")
        if not response["success"]:
            raise RuntimeError(f"Failed to resume the running plan: {response['msg']}")

        def condition(status):
            return status["manager_state"] in ("idle", "executing_queue")

        self._wait_for_completion(
            condition=condition, msg="resume execution of the plan", timeout=timeout
        )

    def _re_continue_plan(self, *, action, timeout=0):

        if action not in ("stop", "abort", "halt"):
            raise RuntimeError(f"Unrecognized action '{action}'")

        method = f"re_{action}"

        response = self._client.send_message(method=method)
        if not response["success"]:
            raise RuntimeError(
                f"Failed to {action} the running plan: {response['msg']}"
            )

        def condition(status):
            return status["manager_state"] == "idle"

        self._wait_for_completion(
            condition=condition, msg=f"{action} the plan", timeout=timeout
        )

    def re_stop(self, timeout=0):
        self._re_continue_plan(action="stop", timeout=timeout)

    def re_abort(self, timeout=0):
        self._re_continue_plan(action="abort", timeout=timeout)

    def re_halt(self, timeout=0):
        self._re_continue_plan(action="halt", timeout=timeout)

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
