import collections
import pprint
import time

from bluesky_live.event import EmitterGroup, Event
from bluesky_queueserver.manager.comms import ZMQCommSendThreads, CommTimeoutError
from bluesky_queueserver.manager.profile_ops import bind_plan_arguments


class RunEngineClient:
    """
    Parameters
    ----------
    zmq_server_address : str or None
        Address of ZMQ server (Run Engine Manager). If None, then the default address defined
        in RE Manager code is used. (Default address is ``tcp://localhost:60615``).
    user_name : str
        Name of the user submitting the plan. The name is saved as a parameter of the queue item
        and identifies the user submitting the plan (may be important in multiuser systems).
    user_group : str
        Name of the user group. User group is saved as a parameter of a queue item. Each user group
        can be assigned permissions to use a restricted set of plans and pass a restricted set of
        devices as plan parameters. Groups and group permissions are defined in the file
        ``user_group_permissions.yaml`` (see documentation for RE Manager).
    """

    def __init__(
        self, zmq_server_address=None, user_name="GUI Client", user_group="admin"
    ):
        self._client = ZMQCommSendThreads(zmq_server_address=zmq_server_address)
        self.set_map_param_labels_to_keys()

        # User name and group are hard coded for now
        self._user_name = user_name
        self._user_group = user_group

        self._re_manager_status = {}
        self._re_manager_connected = None
        self._re_manager_status_time = time.time()
        # Minimum period of status update (avoid excessive call frequency)
        self._re_manager_status_update_period = 0.2

        self._allowed_devices = {}
        self._allowed_plans = {}
        self._plan_queue_items = []
        # Dictionary key: item uid, value: item pos in queue:
        self._plan_queue_items_pos = {}
        self._running_item = {}
        self._plan_queue_uid = ""
        self._run_list = []
        self._run_list_uid = ""
        self._plan_history_items = []
        self._plan_history_uid = ""

        # UID of the selected queue item, "" if no items are selected
        self._selected_queue_item_uid = ""
        # History items are addressed by position (there could be repeated UIDs in the history)
        #   Items in the history can not be moved or deleted, only added to the bottom, so
        #   using positions is consistent.
        self._selected_history_item_pos = -1

        self.events = EmitterGroup(
            source=self,
            status_changed=Event,
            plan_queue_changed=Event,
            running_item_changed=Event,
            plan_history_changed=Event,
            allowed_devices_changed=Event,
            allowed_plans_changed=Event,
            queue_item_selection_changed=Event,
            history_item_selection_changed=Event,
        )

    @property
    def re_manager_status(self):
        return self._re_manager_status

    @property
    def re_manager_connected(self):
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

    def load_re_manager_status(self, *, unbuffered=False):
        if unbuffered or (
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
                new_run_list_uid = self._re_manager_status.get("run_list_uid", "")
                if new_run_list_uid != self._run_list_uid:
                    self.load_run_list()
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
                method="devices_allowed",
                params={"user_group": self._user_group},
                raise_exceptions=True,
            )
            if result["success"] is False:
                raise RuntimeError(
                    f"Failed to load list of allowed devices: {result['msg']}"
                )
            self._allowed_devices.clear()
            self._allowed_devices.update(result["devices_allowed"])
            self.events.allowed_devices_changed(allowed_devices=self._allowed_devices)
        except Exception as ex:
            print(f"Exception: {ex}")

    def load_allowed_plans(self):
        try:
            result = self._client.send_message(
                method="plans_allowed",
                params={"user_group": self._user_group},
                raise_exceptions=True,
            )
            if result["success"] is False:
                raise RuntimeError(
                    f"Failed to load list of allowed plans: {result['msg']}"
                )
            self._allowed_plans.clear()
            self._allowed_plans.update(result["plans_allowed"])
            self.events.allowed_plans_changed(allowed_plans=self._allowed_plans)
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

            # The dictionary that relates item uids and their positions in the queue.
            #   Used to speed up computations during queue operations.
            self._plan_queue_items_pos = {
                item["item_uid"]: n
                for n, item in enumerate(self._plan_queue_items)
                if "item_uid" in item
            }

            # Deselect queue item if it is not present in the queue
            #   Selection will be cleared when the table is reloaded, so save it in local variable
            selected_uid = self.selected_queue_item_uid
            if self.queue_item_uid_to_pos(selected_uid) < 0:
                selected_uid = ""

            # Update the representation of the queue
            self.events.plan_queue_changed(
                plan_queue_items=self._plan_queue_items,
                selected_item_uid=selected_uid,
            )
            self.events.running_item_changed(
                running_item=self._running_item,
                run_list=self._run_list,
            )

        except Exception as ex:
            print(f"Exception: {ex}")

    def load_run_list(self):
        try:
            result = self._client.send_message(method="re_runs", raise_exceptions=True)
            if result["success"] is False:
                raise RuntimeError(f"Failed to load run_list: {result['msg']}")
            self._run_list.clear()
            self._run_list.extend(result["run_list"])
            self._run_list_uid = result["run_list_uid"]

            self.events.running_item_changed(
                running_item=self._running_item,
                run_list=self._run_list,
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

            # Deselect queue history if it does not exist in the queue
            #   Selection will be cleared when the table is reloaded, so save it in local variable
            selected_item_pos = self.selected_history_item_pos
            if selected_item_pos >= len(self._plan_history_items):
                selected_item_pos = -1

            self.events.plan_history_changed(
                plan_history_items=self._plan_history_items.copy(),
                selected_item_pos=selected_item_pos,
            )

        except Exception as ex:
            print(f"Exception: {ex}")

    # ============================================================================
    #                         Item representation

    def set_map_param_labels_to_keys(self, *, map_dict=None):
        """
        Set mapping between labels and item dictionary keys. Map is a dictionary where
        keys are label names (e.g. names of the columns of a table) and dictionaries are
        tuples of keys that show the location of the parameter in item dictionary, e.g.
        ``{"STATUS": ("result", "exit_status")}``. In most practical cases this function
        should not be called at all.

        Parameters
        ----------
        map_dict : dict or None
            Map dictionary or None to use the default dictionary

        Returns
        -------
        None
        """
        if (map_dict is not None) and not isinstance(map_dict, collections.abc.Mapping):
            raise ValueError(
                f"Incorrect type ('{type(map_dict)}') of the parameter 'map'. 'None' or 'dict' is expected"
            )

        _default_map = {
            "": ("item_type",),
            "Name": ("name",),
            "Parameters": ("kwargs",),
            "USER": ("user",),
            "GROUP": ("user_group",),
            "STATUS": ("result", "exit_status"),
        }
        map_dict = map_dict if (map_dict is not None) else _default_map
        self._map_column_labels_to_keys = map_dict

    def get_item_value_for_label(self, *, item, label, as_str=True):
        """
        Returns parameter value of the item for given label (e.g. table column name). Returns
        value represented as a string if `as_str=True`, otherwise returns value itself. Raises
        `KeyError` if the label or parameter is not found. It is not guaranteed that item
        dictionaries always contain all parameters, so exception does not indicate an error
        and should be processed by application.

        Parameters
        ----------
        item : dict
            Dictionary containing item parameters
        label : str
            Label (e.g. table column name)
        as_str : boolean
            ``True`` - return string representation of the value, otherwise return the value

        Returns
        -------
        str
            column value represented as a string

        Raises
        ------
        KeyError
            label or parameter is not found in the dictionary
        """
        try:
            key_seq = self._map_column_labels_to_keys[label]
        except KeyError:
            raise KeyError("Label 'label' is not found in the map dictionary")

        # Follow the path in the dictionary. 'KeyError' exception is raised if a key does not exist
        try:
            value = item
            item_name, item_type = item.get("name", ""), item.get("item_type", "")
            if (len(key_seq) == 1) and (key_seq[-1] in ("args", "kwargs")):
                # Special case: combine args and kwargs to be displayed in one column
                value = {
                    "args": value.get("args", []),
                    "kwargs": value.get("kwargs", {}),
                }
            else:
                for key in key_seq:
                    value = value[key]
        except KeyError:
            raise KeyError(
                f"Parameter with keys {key_seq} is not found in the item dictionary"
            )

        if as_str:
            key = key_seq[-1]

            s = ""
            if key in ("args", "kwargs"):
                try:
                    if item_type == "plan":
                        plan_parameters = self._allowed_plans.get(item_name, None)
                        if plan_parameters is None:
                            raise RuntimeError(
                                f"Plan '{item_name}' is not in the list of allowed plans"
                            )
                        bound_arguments = bind_plan_arguments(
                            plan_args=value["args"],
                            plan_kwargs=value["kwargs"],
                            plan_parameters=plan_parameters,
                        )
                        # If the arguments were bound successfully, then replace 'args' and 'kwargs'.
                        value["args"] = []
                        value["kwargs"] = bound_arguments.arguments
                except Exception as ex:
                    print(
                        f"Failed to bind arguments (item_type='{item_type}', "
                        f"item_name='{item_name}'). Exception: {ex}"
                    )

                s_args, s_kwargs = "", ""
                if value["args"] and isinstance(
                    value["args"], collections.abc.Iterable
                ):
                    s_args = ", ".join(f"{v}" for v in value["args"])
                if value["kwargs"] and isinstance(
                    value["kwargs"], collections.abc.Mapping
                ):
                    s_kwargs = ", ".join(
                        f"{k}: {v}" for k, v in value["kwargs"].items()
                    )
                s = ", ".join([_ for _ in [s_args, s_kwargs] if _])
            elif key == "args":
                if value and isinstance(value, collections.abc.Iterable):
                    s = ", ".join(f"{v}" for v in value)
            elif key == "item_type":
                # Print capitalized first letter of the item type ('P' or 'I')
                s_tmp = str(value)
                if s_tmp:
                    s = s_tmp[0].upper()
            else:
                s = str(value)
        else:
            s = value

        return s

    # ============================================================================
    #                         Queue operations

    @property
    def selected_queue_item_uid(self):
        return self._selected_queue_item_uid

    @selected_queue_item_uid.setter
    def selected_queue_item_uid(self, item_uid):
        if self._selected_queue_item_uid != item_uid:
            self._selected_queue_item_uid = item_uid
            self.events.queue_item_selection_changed(selected_item_uid=item_uid)

    def queue_item_uid_to_pos(self, item_uid):
        # Returns -1 if item was not found
        return self._plan_queue_items_pos.get(item_uid, -1)

    def queue_item_pos_to_uid(self, n_item):
        try:
            item_uid = self._plan_queue_items[n_item]["item_uid"]
        except Exception:
            item_uid = ""
        return item_uid

    def queue_item_move_up(self):
        """
        Move plan up in the queue by one positon
        """
        item_uid = self.selected_queue_item_uid
        n_item = self.queue_item_uid_to_pos(item_uid)
        n_items = len(self._plan_queue_items)
        if item_uid and (n_items > 1) and (n_item > 0):
            n_item_above = n_item - 1
            item_uid_above = self.queue_item_pos_to_uid(n_item_above)
            response = self._client.send_message(
                method="queue_item_move",
                params={"uid": item_uid, "before_uid": item_uid_above},
            )
            self.load_re_manager_status(unbuffered=True)
            if not response["success"]:
                raise RuntimeError(f"Failed to move the item: {response['msg']}")

    def queue_item_move_down(self):
        """
        Move plan down in the queue by one positon
        """
        item_uid = self.selected_queue_item_uid
        n_item = self.queue_item_uid_to_pos(item_uid)
        n_items = len(self._plan_queue_items)
        if item_uid and (n_items > 1) and (0 <= n_item < n_items - 1):
            n_item_below = n_item + 1
            item_uid_below = self.queue_item_pos_to_uid(n_item_below)
            response = self._client.send_message(
                method="queue_item_move",
                params={"uid": item_uid, "after_uid": item_uid_below},
            )
            self.load_re_manager_status(unbuffered=True)
            if not response["success"]:
                raise RuntimeError(f"Failed to move the item: {response['msg']}")

    def queue_item_move_in_place_of(self, item_uid_to_replace):
        """
        Replace plan with given UID with the selected plan
        """
        item_uid = self.selected_queue_item_uid
        n_item = self.queue_item_uid_to_pos(item_uid)
        n_item_to_replace = self.queue_item_uid_to_pos(item_uid_to_replace)
        if (
            item_uid
            and item_uid_to_replace
            and (n_item_to_replace >= 0)
            and (item_uid != item_uid_to_replace)
        ):
            location = "before_uid" if (n_item_to_replace < n_item) else "after_uid"
            response = self._client.send_message(
                method="queue_item_move",
                params={"uid": item_uid, location: item_uid_to_replace},
            )
            self.load_re_manager_status(unbuffered=True)
            if not response["success"]:
                raise RuntimeError(f"Failed to move the item: {response['msg']}")

    def queue_item_move_to_top(self):
        """
        Move plan to top of the queue
        """
        item_uid = self.selected_queue_item_uid
        if item_uid:
            response = self._client.send_message(
                method="queue_item_move", params={"uid": item_uid, "pos_dest": "front"}
            )
            self.load_re_manager_status(unbuffered=True)
            if not response["success"]:
                raise RuntimeError(f"Failed to move the item: {response['msg']}")

    def queue_item_move_to_bottom(self):
        """
        Move plan to top of the queue
        """
        item_uid = self.selected_queue_item_uid
        if item_uid:
            response = self._client.send_message(
                method="queue_item_move", params={"uid": item_uid, "pos_dest": "back"}
            )
            self.load_re_manager_status(unbuffered=True)
            if not response["success"]:
                raise RuntimeError(f"Failed to move the item: {response['msg']}")

    def queue_item_remove(self):
        """
        Delete item from queue
        """
        item_uid = self.selected_queue_item_uid
        if item_uid:
            # Find and set UID of an item that will be selected once the current item is removed
            n_item = self.queue_item_uid_to_pos(item_uid)
            n_items = len(self._plan_queue_items)
            if n_items <= 1:
                n_sel_item_new = -1
            elif n_item < n_items - 1:
                n_sel_item_new = n_item + 1
            else:
                n_sel_item_new = n_item - 1
            self.selected_queue_item_uid = self.queue_item_pos_to_uid(n_sel_item_new)

            response = self._client.send_message(
                method="queue_item_remove", params={"uid": item_uid}
            )
            self.load_re_manager_status(unbuffered=True)
            if not response["success"]:
                raise RuntimeError(f"Failed to delete item: {response['msg']}")

    def queue_clear(self):
        """
        Clear the plan queue
        """
        response = self._client.send_message(
            method="queue_clear",
        )
        self.load_re_manager_status(unbuffered=True)
        if not response["success"]:
            raise RuntimeError(f"Failed to clear the queue: {response['msg']}")

    def queue_mode_loop_enable(self, enable):
        """
        Enable or disable LOOP mode of the queue
        """
        response = self._client.send_message(
            method="queue_mode_set", params={"mode": {"loop": enable}}
        )
        self.load_re_manager_status(unbuffered=True)
        if not response["success"]:
            raise RuntimeError(f"Failed to change plan queue mode: {response['msg']}")

    def queue_item_copy_to_queue(self):
        """
        Copy currently selected item to queue. Item is supposed to be selected in the plan queue.
        """
        sel_item_uid = self._selected_queue_item_uid
        sel_item_pos = self.queue_item_uid_to_pos(sel_item_uid)
        if sel_item_uid and (sel_item_pos >= 0):
            item = self._plan_queue_items[sel_item_pos]
            self.queue_item_add(item=item)

    def queue_item_add(self, *, item, params=None):
        """
        Add item to queue. This function should be called by all widgets that add items to queue.
        The new item is inserted after the selected item or to the back of the queue in case
        no item is selected. Optional dictionary `params` may be used to override the default
        behavior. E.g. ``params={"pos": "front"}`` will add the item to the font of the queue.
        See the documentation for ``queue_item_add`` 0MQ API of Queue Server.
        The new item becomes the selected item.
        """
        sel_item_uid = self._selected_queue_item_uid
        queue_is_empty = not len(self._plan_queue_items)
        if not params:
            if queue_is_empty or not sel_item_uid:
                # Push button to the back of the queue
                params = {}
            else:
                params = {"after_uid": sel_item_uid}

        # We are submitting a plan as a new plan, so all unnecessary data will be stripped
        #   and new item UID will be assigned.
        request_params = {
            "item": item,
            "user": self._user_name,
            "user_group": self._user_group,
        }
        request_params.update(params)
        response = self._client.send_message(
            method="queue_item_add", params=request_params
        )
        self.load_re_manager_status(unbuffered=True)
        if not response["success"]:
            raise RuntimeError(f"Failed to add item to the queue: {response['msg']}")
        else:
            try:
                # The 'item' and 'item_uid' should always be included in the returned item in case of success.
                sel_item_uid = response["item"]["item_uid"]
            except KeyError as ex:
                print(
                    f"Item or item UID is not found in the server response {pprint.pformat(response)}. "
                    f"Can not update item selection in the queue table. Exception: {ex}"
                )
            self.selected_queue_item_uid = sel_item_uid

    # ============================================================================
    #                         History operations

    @property
    def selected_history_item_pos(self):
        return self._selected_history_item_pos

    @selected_history_item_pos.setter
    def selected_history_item_pos(self, item_pos):
        if self._selected_history_item_pos != item_pos:
            self._selected_history_item_pos = item_pos
            self.events.history_item_selection_changed(selected_item_pos=item_pos)

    def history_item_add_to_queue(self):
        """Copy the selected plan from history to the end of the queue"""
        selected_item_pos = self.selected_history_item_pos
        if selected_item_pos >= 0:
            history_item = self._plan_history_items[selected_item_pos]
            self.queue_item_add(item=history_item)

    def history_clear(self):
        """
        Clear history
        """
        response = self._client.send_message(
            method="history_clear",
        )
        self.load_re_manager_status(unbuffered=True)
        if not response["success"]:
            raise RuntimeError(f"Failed to clear the history: {response['msg']}")

    # ============================================================================
    #                     Operations with running item

    def running_item_add_to_queue(self):
        """Copy the selected plan from history to the end of the queue"""
        if self._running_item:
            running_item = self._running_item.copy()
            self.queue_item_add(item=running_item)

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
