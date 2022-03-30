import collections
import copy
import os.path
import pprint
import time
import importlib

from bluesky_live.event import EmitterGroup, Event
from bluesky_queueserver import ZMQCommSendThreads, CommTimeoutError, bind_plan_arguments, ReceiveConsoleOutput
from bluesky_queueserver.manager.conversions import spreadsheet_to_plan_list


class RunEngineClient:
    """
    Parameters
    ----------
    zmq_server_address : str or None
        Address of ZMQ server (Run Engine Manager). If None, then the default address defined
        in RE Manager code is used. (Default address is ``tcp://localhost:60615``).
    zmq_subscribe_address : str or None
        ZMQ address of the socket used by RE Manager to publishe console output.
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
        self, zmq_server_address=None, zmq_subscribe_address=None, user_name="GUI Client", user_group="admin"
    ):
        self._client = ZMQCommSendThreads(zmq_server_address=zmq_server_address)
        self.set_map_param_labels_to_keys()

        # Address of remote 0MQ socket used to publish RE Manager console output
        self._zmq_subscribe_addr = zmq_subscribe_address
        self._stop_console_monitor = False

        # User name and group are hard coded for now
        self._user_name = user_name
        self._user_group = user_group

        self._re_manager_status = {}
        self._re_manager_connected = None
        self._re_manager_status_time = time.time()
        # Minimum period of status update (avoid excessive call frequency)
        self._re_manager_status_update_period = 0.2

        self._allowed_devices = {}
        self._allowed_devices_uid = ""
        self._allowed_plans = {}
        self._allowed_plans_uid = ""
        self._plan_queue_items = []
        # Dictionary key: item uid, value: item pos in queue:
        self._plan_queue_items_pos = {}
        self._running_item = {}
        self._plan_queue_uid = ""
        self._run_list = []
        self._run_list_uid = ""
        self._plan_history_items = []
        self._plan_history_uid = ""

        # List of UIDs of the selected queue items, [] if no items are selected
        self._selected_queue_item_uids = []
        # History items are addressed by position (there could be repeated UIDs in the history)
        #   Items in the history can not be moved or deleted, only added to the bottom, so
        #   using positions is consistent. Empty list - no items are selected
        self._selected_history_item_pos = []

        # Current directory (used for opening/saving files).
        self.current_dir = None
        # Set the variable to the name of the Queue Server Custom Module (if available)
        self.qserver_custom_module_name = None
        # List of spreadsheet data types
        self.plan_spreadsheet_data_types = None
        # Dictionary of additional parameters: key - parameter name, value - a dictionary with
        #   the following key/value pairs: "text" - text description of the parameter to use in the form,
        #   "values" -  a list or a tuple of values, "type" - type of the value.
        self.plan_spreadsheet_additional_parameters = {}

        # Indicates if operation of destroying an environment is activated.
        self._env_destroy_activated = False

        # TODO: in the future the list of allowed instructions should be requested from the server
        self._allowed_instructions = {
            "queue_stop": {
                "name": "queue_stop",
                "description": "Stop execution of the queue.",
            }
        }

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
            history_item_process=Event,
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
        if unbuffered or (time.time() - self._re_manager_status_time > self._re_manager_status_update_period):
            status = self._re_manager_status.copy()
            accessible = self._re_manager_connected
            try:
                new_manager_status = self._client.send_message(method="status", raise_exceptions=True)
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
                new_allowed_plans_uid = self._re_manager_status.get("plans_allowed_uid", "")
                if new_allowed_plans_uid != self._allowed_plans_uid:
                    self.load_allowed_plans()
                new_allowed_devices_uid = self._re_manager_status.get("devices_allowed_uid", "")
                if new_allowed_devices_uid != self._allowed_devices_uid:
                    self.load_allowed_devices()

            except CommTimeoutError:
                self._re_manager_connected = False
            if (status != self._re_manager_status) or (accessible != self._re_manager_connected):
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
                raise RuntimeError(f"Failed to load list of allowed devices: {result['msg']}")
            self._allowed_devices.clear()
            self._allowed_devices.update(result["devices_allowed"])
            self._allowed_devices_uid = result["devices_allowed_uid"]
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
                raise RuntimeError(f"Failed to load list of allowed plans: {result['msg']}")
            self._allowed_plans.clear()
            self._allowed_plans.update(result["plans_allowed"])
            self._allowed_plans_uid = result["plans_allowed_uid"]
            self.events.allowed_plans_changed(allowed_plans=self._allowed_plans)
        except Exception as ex:
            print(f"Exception: {ex}")

    def load_plan_queue(self):
        try:
            result = self._client.send_message(method="queue_get", raise_exceptions=True)
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
                item["item_uid"]: n for n, item in enumerate(self._plan_queue_items) if "item_uid" in item
            }

            # Deselect queue items that are not in the queue or are not part of the contiguous
            #   selection. The selection will be cleared when the table is reloaded, so save
            #   it in local variable.
            selected_uids = self.selected_queue_item_uids
            pos, uids = -1, []
            for uid in selected_uids:
                p = self.queue_item_uid_to_pos(uid)
                if p >= 0:
                    if (pos < 0) or ((p >= 0) and (p == pos + 1)):
                        pos = p
                        uids.append(uid)
                    else:
                        break
            self.selected_queue_item_uids = uids

            # Update the representation of the queue
            self.events.plan_queue_changed(
                plan_queue_items=self._plan_queue_items,
                selected_item_uids=self.selected_queue_item_uids.copy(),
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
            result = self._client.send_message(method="history_get", raise_exceptions=True)
            if result["success"] is False:
                raise RuntimeError(f"Failed to load history: {result['msg']}")
            self._plan_history_items.clear()
            self._plan_history_items.extend(result["items"])
            self._plan_history_uid = result["plan_history_uid"]

            # Deselect queue history if it does not exist in the queue
            #   Selection will be cleared when the table is reloaded, so save it in local variable
            selected_item_pos = self.selected_history_item_pos
            if selected_item_pos and (selected_item_pos[-1] >= len(self._plan_history_items)):
                selected_item_pos = []
                self.selected_history_item_pos = selected_item_pos

            self.events.plan_history_changed(
                plan_history_items=self._plan_history_items.copy(),
                selected_item_pos=self.selected_history_item_pos,
            )

        except Exception as ex:
            print(f"Exception: {ex}")

    # ============================================================================
    #                       Useful functions
    def get_allowed_plan_parameters(self, *, name):
        """
        Returns the dictionary of parameters for the plan with name ``name`` from
        the list of allowed plans. Returns ``None`` if plan is not found in the list

        Parameters
        ----------
        name : str
            name of the plan

        Returns
        -------
        dict or None
            dictionary of plan parameters or ``None`` if the plan is not in the list.
        """
        return self._allowed_plans.get(name, None)

    def get_allowed_instruction_parameters(self, *, name):
        """
        Returns the dictionary of parameters for the instruction with name ``name`` from
        the list of allowed instructions. Returns ``None`` if plan is not found in the list

        Parameters
        ----------
        name : str
            name of the instruction

        Returns
        -------
        dict or None
            dictionary of instruction parameters or ``None`` if the plan is not in the list.
        """
        return self._allowed_instructions.get(name, None)

    def get_allowed_plan_names(self):
        return list(self._allowed_plans.keys()) if self._allowed_plans else []

    def get_allowed_instruction_names(self):
        return list(("queue_stop",))

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

    def get_bound_item_arguments(self, item):
        item_args = item.get("args", [])
        item_kwargs = item.get("kwargs", {})
        item_type = item.get("item_type", None)
        item_name = item.get("name", None)

        try:
            if item_type == "plan":
                plan_parameters = self._allowed_plans.get(item_name, None)
                if plan_parameters is None:
                    raise RuntimeError(f"Plan '{item_name}' is not in the list of allowed plans")
                bound_arguments = bind_plan_arguments(
                    plan_args=item_args,
                    plan_kwargs=item_kwargs,
                    plan_parameters=plan_parameters,
                )
                # If the arguments were bound successfully, then replace 'args' and 'kwargs'.
                item_args = []
                item_kwargs = bound_arguments.arguments
        except Exception:
            # print(
            #     f"Failed to bind arguments (item_type='{item_type}', "
            #     f"item_name='{item_name}'). Exception: {ex}"
            # )
            pass

        return item_args, item_kwargs

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
            raise KeyError(f"Label '{label}' is not found in the map dictionary")

        # Follow the path in the dictionary. 'KeyError' exception is raised if a key does not exist
        try:
            value = item
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
            raise KeyError(f"Parameter with keys {key_seq} is not found in the item dictionary")

        if as_str:
            key = key_seq[-1]

            s = ""
            if key in ("args", "kwargs"):
                value["args"], value["kwargs"] = self.get_bound_item_arguments(item)

                s_args, s_kwargs = "", ""
                if value["args"] and isinstance(value["args"], collections.abc.Iterable):
                    s_args = ", ".join(f"{v}" for v in value["args"])
                if value["kwargs"] and isinstance(value["kwargs"], collections.abc.Mapping):
                    s_kwargs = ", ".join(f"{k}: {v}" for k, v in value["kwargs"].items())
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
    def selected_queue_item_uids(self):
        return self._selected_queue_item_uids

    @selected_queue_item_uids.setter
    def selected_queue_item_uids(self, item_uids):
        if self._selected_queue_item_uids != item_uids:
            self._selected_queue_item_uids = item_uids.copy()
            self.events.queue_item_selection_changed(selected_item_uids=item_uids)

    def queue_item_uid_to_pos(self, item_uid):
        # Returns -1 if item was not found
        return self._plan_queue_items_pos.get(item_uid, -1)

    def queue_item_pos_to_uid(self, n_item):
        try:
            item_uid = self._plan_queue_items[n_item]["item_uid"]
        except Exception:
            item_uid = ""
        return item_uid

    def queue_item_by_uid(self, item_uid):
        """
        Returns deep copy of the item based on item UID or None if the item was not found.

        Parameters
        ----------
        item_uid : str
            UID of an item. If ``item_uid=""`` then None will be returned

        Returns
        -------
        dict or None
            Dictionary of item parameters or ``None`` if the item was not found
        """
        if item_uid:
            sel_item_pos = self.queue_item_uid_to_pos(item_uid)
            if sel_item_pos >= 0:
                return copy.deepcopy(self._plan_queue_items[sel_item_pos])
        return None

    def _queue_items_move(self, *, sel_items, ref_item, position):
        """
        Move the batch of selected items above or below the reference item. The target item
        should not belong to the batch of items.

        Parameters
        ----------
        sel_items : list
            the list of selected item UIDs
        ref_item : str
            UID of the reference item
        position : str
            "before" - the items are moved above the target item, "after" - below the traget item
        """
        supported_positions = ("before", "after")
        if position not in supported_positions:
            raise ValueError(f"Unsupported position: {position}, supported values: {supported_positions}")

        if not sel_items or (ref_item in sel_items):
            return  # Nothing to do

        params = {"uids": sel_items}
        if position == "before":
            params.update({"before_uid": ref_item})
        else:
            params.update({"after_uid": ref_item})

        response = self._client.send_message(method="queue_item_move_batch", params=params)
        self.load_re_manager_status(unbuffered=True)

        if response["success"]:
            try:
                sel_items = [_["item_uid"] for _ in response["items"]]
            except Exception as ex:
                print(f"Item UID is not found in some items returned by the Queue Server: {ex}")

            self.selected_queue_item_uids = sel_items

        else:
            raise RuntimeError(f"Failed to move the item: {response['msg']}")

    def queue_items_move_up(self):
        """
        Move the selected batch of items up by one position
        """
        n_items = len(self._plan_queue_items)
        n_sel_items = len(self.selected_queue_item_uids)
        if not n_items or not n_sel_items or (n_items - n_sel_items < 1):
            return

        item_uid = self.selected_queue_item_uids[0]
        n_item = self.queue_item_uid_to_pos(item_uid)
        if item_uid and (n_item > 0):
            n_item_above = n_item - 1
            item_uid_above = self.queue_item_pos_to_uid(n_item_above)
            self._queue_items_move(
                sel_items=self._selected_queue_item_uids, ref_item=item_uid_above, position="before"
            )

    def queue_items_move_down(self):
        """
        Move the selected batch of items down by one position
        """
        n_items = len(self._plan_queue_items)
        n_sel_items = len(self.selected_queue_item_uids)
        if not n_items or not n_sel_items or (n_items - n_sel_items < 1):
            return

        item_uid = self.selected_queue_item_uids[-1]
        n_item = self.queue_item_uid_to_pos(item_uid)
        if item_uid and (0 <= n_item < n_items - 1):
            n_item_below = n_item + 1
            item_uid_below = self.queue_item_pos_to_uid(n_item_below)
            self._queue_items_move(
                sel_items=self._selected_queue_item_uids, ref_item=item_uid_below, position="after"
            )

    def queue_items_move_in_place_of(self, uid_ref_item):
        """
        Move the selected batch of items in the queue so that the first item of the batch assumes
        the position of the reference item. This is a generic 'move' operation. The reference item
        must not be included in the selected batch.
        """
        n_items = len(self._plan_queue_items)
        n_sel_items = len(self.selected_queue_item_uids)
        if not n_items or not n_sel_items or (n_items - n_sel_items < 1):
            return

        sel_item_uid_top = self.selected_queue_item_uids[0]
        sel_item_uid_bottom = self.selected_queue_item_uids[-1]
        n_item_top = self.queue_item_uid_to_pos(sel_item_uid_top)
        n_item_bottom = self.queue_item_uid_to_pos(sel_item_uid_bottom)
        n_item_to_replace = self.queue_item_uid_to_pos(uid_ref_item)

        if (n_item_to_replace < n_item_top) or (n_item_to_replace > n_item_bottom):
            position = "before" if (n_item_to_replace < n_item_top) else "after"
            self._queue_items_move(
                sel_items=self._selected_queue_item_uids, ref_item=uid_ref_item, position=position
            )

    def queue_items_move_to_top(self):
        """
        Move the selected batch of items to the top of the queue
        """
        if not self._plan_queue_items:
            return
        self.queue_items_move_in_place_of(self._plan_queue_items[0].get("item_uid", ""))

    def queue_items_move_to_bottom(self):
        """
        Move the selected batch of items to the bottom of the queue
        """
        if not self._plan_queue_items:
            return
        self.queue_items_move_in_place_of(self._plan_queue_items[-1].get("item_uid", ""))

    def queue_items_remove(self):
        """
        Delete the selected batch of items from queue.
        """
        sel_item_uids = self.selected_queue_item_uids.copy()
        if sel_item_uids:
            # Find and set UID of an item that will be selected once the current item is removed
            sel_item_uid_top = sel_item_uids[0]
            sel_item_uid_bottom = sel_item_uids[-1]
            n_item_top = self.queue_item_uid_to_pos(sel_item_uid_top)
            n_item_bottom = self.queue_item_uid_to_pos(sel_item_uid_bottom)

            n_items = len(self._plan_queue_items)

            if n_items <= 1:
                n_sel_item_new = -1
            elif n_item_bottom < n_items - 1:
                n_sel_item_new = n_item_bottom + 1
            else:
                n_sel_item_new = n_item_top - 1

            sel_item_new_uid = self.queue_item_pos_to_uid(n_sel_item_new)
            if sel_item_new_uid:
                self.selected_queue_item_uids = [sel_item_new_uid]
            else:
                self.selected_queue_item_uids = []

            response = self._client.send_message(method="queue_item_remove_batch", params={"uids": sel_item_uids})
            self.load_re_manager_status(unbuffered=True)
            if not response["success"]:
                print(f"Failed to delete item: {response['msg']}")

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
        response = self._client.send_message(method="queue_mode_set", params={"mode": {"loop": enable}})
        self.load_re_manager_status(unbuffered=True)
        if not response["success"]:
            raise RuntimeError(f"Failed to change plan queue mode: {response['msg']}")

    def queue_item_copy_to_queue(self):
        """
        Copy currently selected item to queue. Item is supposed to be selected in the plan queue.
        """
        sel_item_uids = self._selected_queue_item_uids
        sel_items = []
        for uid in sel_item_uids:
            pos = self.queue_item_uid_to_pos(uid)
            if uid and (pos >= 0):
                sel_items.append(self._plan_queue_items[pos])
        if sel_items:
            self.queue_item_add_batch(items=sel_items)

    def queue_item_add(self, *, item, params=None):
        """
        Add item to queue. This function should be called by all widgets that add items to queue.
        The new item is inserted after the selected item or to the back of the queue in case
        no item is selected. Optional dictionary `params` may be used to override the default
        behavior. E.g. ``params={"pos": "front"}`` will add the item to the font of the queue.
        See the documentation for ``queue_item_add`` 0MQ API of Queue Server.
        The new item becomes the selected item.
        """
        if self._selected_queue_item_uids:
            # Insert after the last item in the selected batch
            sel_item_uid = self._selected_queue_item_uids[-1]
        else:
            # No selection: push to the back of the queue
            sel_item_uid = None

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
        response = self._client.send_message(method="queue_item_add", params=request_params)
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
            self.selected_queue_item_uids = [sel_item_uid]

    def queue_item_update(self, *, item):
        """
        Update the existing plan in the queue. This function should be called by all widgets
        that are used to modify (edit) the existing queue items. The items are distinguished by
        item UID, so item UID in the submitted ``item`` must match UID of the existing queue item
        that is replaced. The modified item becomes a selected item.
        """
        # We are submitting a plan as a new plan, so all unnecessary data will be stripped
        #   and new item UID will be assigned.
        request_params = {
            "item": item,
            "user": self._user_name,
            "user_group": self._user_group,
            "replace": True,  # Generates new UID
        }
        response = self._client.send_message(method="queue_item_update", params=request_params)
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
            self.selected_queue_item_uids = [sel_item_uid]

    def queue_item_add_batch(self, *, items, params=None):
        """
        Add a batch of items to queue. This function should be called by all widgets that
        add a batch of items to queue. The new set of items added to the back of the queue.
        inserted after the selected item or to the back of the queue in case no item is selected.
        Optional dictionary `params` may be used to override the default behavior.
        E.g. ``params={"pos": "front"}`` will add the item to the font of the queue.
        See the documentation for ``queue_item_add_batch`` 0MQ API of Queue Server.
        The newly inserted items becomes selected.
        """
        # Do nothing if no items are to be inserted
        if not items:
            return

        sel_item_uids = self.selected_queue_item_uids.copy()

        if sel_item_uids:
            # Insert after the last item in the selected batch
            sel_item_uid = sel_item_uids[-1]
        else:
            # No selection: push to the back of the queue
            sel_item_uid = None

        queue_is_empty = not len(self._plan_queue_items)
        if not params:
            if queue_is_empty or not sel_item_uid:
                # Push button to the back of the queue
                params = {}
            else:
                params = {"after_uid": sel_item_uid}

        # We are submitting the plans in the batch as new plans, so all unnecessary
        #   data will be stripped and the new item UID will be assigned.
        request_params = {
            "items": items,
            "user": self._user_name,
            "user_group": self._user_group,
        }
        request_params.update(params)
        response = self._client.send_message(method="queue_item_add_batch", params=request_params)
        self.load_re_manager_status(unbuffered=True)
        if not response["success"]:
            raise RuntimeError(f"Failed to add the batch of item to the queue: {response['msg']}")
        else:
            try:
                # The 'item' and 'item_uid' should always be included in the returned item in case of success.
                sel_item_uids = [_["item_uid"] for _ in response["items"]]
            except KeyError as ex:
                print(
                    f"Item or item UID is not found in some of the items returned by the server "
                    f"{pprint.pformat(response)}. Can not update item selection in the queue table. "
                    f"Exception: {ex}"
                )
            self.selected_queue_item_uids = sel_item_uids

    def queue_upload_spreadsheet(self, *, file_path, data_type=None, **kwargs):
        # ``kwargs``` are passed to the custom spreadsheet processing function
        # TODO: significant part of this function is duplication of the code from
        #   ``bluesky_queueserver.server.server``. Implement reusable function as part of
        #   Queue Server API.

        file_path = os.path.expanduser(file_path)
        file_path = os.path.abspath(file_path)
        _, f_name = os.path.split(file_path)

        with open(file_path, "rb") as f:
            custom_code_module_name = self.qserver_custom_module_name

            custom_code_module = None
            if custom_code_module_name:
                try:
                    print(f"Importing custom module '{custom_code_module_name}' ...")
                    # logger.info("Importing custom module '%s' ...", custom_code_module_name)
                    custom_code_module = importlib.import_module(custom_code_module_name.replace("-", "_"))
                    print(f"Module '{custom_code_module_name}' was imported successfully.")
                    # logger.info("Module '%s' was imported successfully.", custom_code_module_name)
                except Exception as ex:
                    print(f"Failed to import custom instrument module '{custom_code_module_name}': {ex}")
                    # logger.error("Failed to import custom instrument module '%s':
                    # %s", custom_code_module_name, ex)

            item_list = []
            processed = False
            if custom_code_module and ("spreadsheet_to_plan_list" in custom_code_module.__dict__):
                print("Processing spreadsheet using function from external module ...")
                # logger.info("Processing spreadsheet using function from external module ...")
                # Try applying  the custom processing function. Some additional useful data is passed to
                #   the function. Unnecessary parameters can be ignored.
                item_list = custom_code_module.spreadsheet_to_plan_list(
                    spreadsheet_file=f, file_name=f_name, data_type=data_type, user=self._user_name, **kwargs
                )
                # The function is expected to return None if it rejects the file (based on 'data_type').
                #   Then try to apply the default processing function.
                processed = item_list is not None

            if not processed:
                # Apply default spreadsheet processing function.
                # logger.info("Processing spreadsheet using default function ...")
                item_list = spreadsheet_to_plan_list(
                    spreadsheet_file=f, file_name=f_name, data_type=data_type, user=self._user_name
                )

            if item_list is None:
                raise RuntimeError("Failed to process the spreadsheet: unsupported data type or format")

            # Since 'item_list' may be returned by user defined functions, verify the type of the list.
            if not isinstance(item_list, (tuple, list)):
                raise ValueError(
                    f"Spreadsheet processing function returned value of '{type(item_list)}' "
                    f"type instead of 'list' or 'tuple'"
                )

            # Ensure, that 'item_list' is sent as a list
            item_list = list(item_list)

            # Set item type for all items that don't have item type already set (item list may contain
            #   instructions, but it is responsibility of the user to set item types correctly.
            #   By default an item is considered a plan.
            for item in item_list:
                if "item_type" not in item:
                    item["item_type"] = "plan"

            # logger.debug("The following plans were created: %s", pprint.pformat(item_list))

            self.queue_item_add_batch(items=item_list)

    # ============================================================================
    #                         History operations

    @property
    def selected_history_item_pos(self):
        return self._selected_history_item_pos

    @selected_history_item_pos.setter
    def selected_history_item_pos(self, item_pos):
        """
        Sets the list of selected item in history

        Parameters
        ----------
        item_pos : iterable
            List or tuple of indices of the selected history items. Empty list/tuple
            if no items are selected.
        """
        item_pos = list(item_pos)
        if self._selected_history_item_pos != item_pos:
            self._selected_history_item_pos = item_pos
            self.events.history_item_selection_changed(selected_item_pos=item_pos)

    def history_item_add_to_queue(self):
        """Copy the selected plan from history to the end of the queue"""
        selected_item_pos = self.selected_history_item_pos
        if selected_item_pos:
            history_items = [self._plan_history_items[_] for _ in selected_item_pos]
            self.queue_item_add_batch(items=history_items)

    def history_item_send_to_processing(self):
        """
        Emits the event ``history_item_process`` sending the currently selected
        item as a parameter. The function should be called in response to some user
        action on the selected item (e.g. double clicking the item). The event
        can may be received by a widget that performs some processing of the item,
        e.g. loading from data broker and plotting the experimental data
        """
        selected_item_pos = self.selected_history_item_pos
        if selected_item_pos:
            # Copy data before sending it for processing by another model
            history_item = copy.deepcopy(self._plan_history_items[selected_item_pos[0]])
            self.events.history_item_process(item=history_item)

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
            raise RuntimeError(f"RE Manager state must be 'idle': current state: {status['manager_state']}")
        if status["worker_environment_exists"]:
            raise RuntimeError("RE Worker environment already exists")

        # Initiate opening of RE Worker environment
        response = self._client.send_message(method="environment_open")
        if not response["success"]:
            raise RuntimeError(f"Failed to open RE Worker environment: {response['msg']}")

        # Wait for the environment to be created.
        if timeout:
            t_stop = time.time() + timeout
            while True:
                self.load_re_manager_status()
                status2 = self._re_manager_status
                if status2["worker_environment_exists"] and status2["manager_state"] == "idle":
                    break
                if timeout and (time.time() > t_stop):
                    raise RuntimeError("Failed to start RE Worker: timeout occurred")
                time.sleep(0.5)

        self.activate_env_destroy(False)

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
            raise RuntimeError(f"RE Manager state must be 'idle': current state: {status['manager_state']}")
        if not status["worker_environment_exists"]:
            raise RuntimeError("RE Worker environment does not exist")

        # Initiate opening of RE Worker environment
        response = self._client.send_message(method="environment_close")
        if not response["success"]:
            raise RuntimeError(f"Failed to close RE Worker environment: {response['msg']}")

        # Wait for the environment to be created.
        if timeout:
            t_stop = time.time() + timeout
        while True:
            self.load_re_manager_status()
            status2 = self._re_manager_status
            if not status2["worker_environment_exists"] and status2["manager_state"] == "idle":
                break
            if timeout and (time.time() > t_stop):
                raise RuntimeError("Failed to start RE Worker: timeout occurred")
            time.sleep(0.5)

        self.activate_env_destroy(False)

    @property
    def env_destroy_activated(self):
        return self._env_destroy_activated

    def activate_env_destroy(self, state):
        self._env_destroy_activated = bool(state)
        self.events.status_changed(
            status=self._re_manager_status,
            is_connected=self._re_manager_connected,
        )

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
        if not self._env_destroy_activated:
            raise RuntimeError("'Destroy Environment' operation is not activated and can not be executed")

        # Check if RE Worker environment already exists and RE manager is idle.
        self.load_re_manager_status()
        status = self._re_manager_status
        if not status["worker_environment_exists"]:
            raise RuntimeError("RE Worker environment does not exist")

        # Initiate opening of RE Worker environment
        response = self._client.send_message(method="environment_destroy")
        if not response["success"]:
            raise RuntimeError(f"Failed to destroy RE Worker environment: {response['msg']}")

        # Wait for the environment to be created.
        if timeout:
            t_stop = time.time() + timeout
        while True:
            self.load_re_manager_status()
            status2 = self._re_manager_status
            if not status2["worker_environment_exists"] and status2["manager_state"] == "idle":
                break
            if timeout and (time.time() > t_stop):
                raise RuntimeError("Failed to start RE Worker: timeout occurred")
            time.sleep(0.5)

        self.activate_env_destroy(False)

    # ============================================================================
    #                        Queue Control

    def queue_start(self):
        response = self._client.send_message(method="queue_start")
        if not response["success"]:
            raise RuntimeError(f"Failed to start the queue: {response['msg']}")

    def queue_stop(self):
        response = self._client.send_message(method="queue_stop")
        if not response["success"]:
            raise RuntimeError(f"Failed to request stopping the queue: {response['msg']}")

    def queue_stop_cancel(self):
        response = self._client.send_message(method="queue_stop_cancel")
        if not response["success"]:
            raise RuntimeError(f"Failed to cancel request to stop the queue: {response['msg']}")

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
        response = self._client.send_message(method="re_pause", params={"option": option})
        if not response["success"]:
            raise RuntimeError(f"Failed to pause the running plan: {response['msg']}")

        def condition(status):
            return status["manager_state"] in ("idle", "paused")

        self._wait_for_completion(condition=condition, msg="pause the running plan", timeout=timeout)

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

        self._wait_for_completion(condition=condition, msg="resume execution of the plan", timeout=timeout)

    def _re_continue_plan(self, *, action, timeout=0):

        if action not in ("stop", "abort", "halt"):
            raise RuntimeError(f"Unrecognized action '{action}'")

        method = f"re_{action}"

        response = self._client.send_message(method=method)
        if not response["success"]:
            raise RuntimeError(f"Failed to {action} the running plan: {response['msg']}")

        def condition(status):
            return status["manager_state"] == "idle"

        self._wait_for_completion(condition=condition, msg=f"{action} the plan", timeout=timeout)

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

    # ============================================================================
    #                        RE Manager console output

    def start_console_output_monitoring(self):
        self._stop_console_monitor = False
        self._rco = ReceiveConsoleOutput(zmq_subscribe_addr=self._zmq_subscribe_addr, timeout=200)

    def stop_console_output_monitoring(self):
        self._stop_console_monitor = True

    # def console_monitoring_thread(self, *, callback):
    def console_monitoring_thread(self):

        while True:
            try:
                payload = self._rco.recv()
                time, msg = payload.get("time", None), payload.get("msg", None)
                return time, msg

            except TimeoutError:
                pass
            except Exception as ex:
                print(f"Exception occurred: {ex}")

            if self._stop_console_monitor:
                del self._rco
                break
