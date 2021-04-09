import time

from qtpy.QtWidgets import (
    QWidget,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)
from qtpy.QtCore import Qt

from bluesky_widgets.qt.threading import FunctionWorker


class QtReManagerConnection(QWidget):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

        self._lb_connected = QLabel("OFF")

        self._pb_re_manager_connect = QPushButton("Connect")
        self._pb_re_manager_connect.clicked.connect(self._pb_re_manager_connect_clicked)

        self._pb_re_manager_disconnect = QPushButton("Disconnect")
        self._pb_re_manager_disconnect.clicked.connect(
            self._pb_re_manager_disconnect_clicked
        )

        self._group_box = QGroupBox("Queue Server")

        vbox = QVBoxLayout()
        vbox.addWidget(self._lb_connected, alignment=Qt.AlignHCenter)
        vbox.addWidget(self._pb_re_manager_connect)
        vbox.addWidget(self._pb_re_manager_disconnect)

        self._group_box.setLayout(vbox)

        vbox = QVBoxLayout()
        vbox.addWidget(self._group_box)
        self.setLayout(vbox)

        # Thread used to initiate periodic status updates
        self._thread = None
        self.updates_activated = False
        self.update_period = 1  # Status update period in seconds

        self._update_widget_states()
        self.model.events.status_changed.connect(self.on_update_widgets)

    def _update_widget_states(self):
        self._pb_re_manager_connect.setEnabled(not self.updates_activated)
        self._pb_re_manager_disconnect.setEnabled(self.updates_activated)

        # We don't know if the server is online or offline:
        self._lb_connected.setText("-----")

    def on_update_widgets(self, event):
        is_connected = event.is_connected
        text = "-----"
        if is_connected is True:
            text = "ONLINE"
        elif is_connected is False:
            text = "OFFLINE"
        self._lb_connected.setText(text)

    def _pb_re_manager_connect_clicked(self):
        self.updates_activated = True
        self.model.clear_connection_status()
        self._update_widget_states()
        self._start_thread()

    def _pb_re_manager_disconnect_clicked(self):
        self.updates_activated = False

    def _start_thread(self):
        self._thread = FunctionWorker(self._reload_status)
        self._thread.finished.connect(self._reload_complete)
        self._thread.start()

    def _reload_complete(self):
        if self.updates_activated:
            self._start_thread()
        else:
            self.model.clear_connection_status()
            self._update_widget_states()

    def _reload_status(self):
        self.model.load_re_manager_status()
        time.sleep(self.update_period)


class QtReEnvironmentControls(QWidget):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

        self._pb_env_open = QPushButton("Open")
        self._pb_env_open.setEnabled(False)
        self._pb_env_open.clicked.connect(self._pb_env_open_clicked)

        self._pb_env_close = QPushButton("Close")
        self._pb_env_close.setEnabled(False)
        self._pb_env_close.clicked.connect(self._pb_env_close_clicked)

        self._pb_env_destroy = QPushButton("Destroy")
        self._pb_env_destroy.setEnabled(False)
        self._pb_env_destroy.clicked.connect(self._pb_env_destroy_clicked)

        self._group_box = QGroupBox("Environment")

        vbox = QVBoxLayout()
        vbox.addWidget(self._pb_env_open)
        vbox.addWidget(self._pb_env_close)
        vbox.addWidget(self._pb_env_destroy)

        self._group_box.setLayout(vbox)

        vbox = QVBoxLayout()
        vbox.addWidget(self._group_box)
        self.setLayout(vbox)

        self.model.events.status_changed.connect(self.on_update_widgets)

    def on_update_widgets(self, event):
        # None should be converted to False:
        is_connected = bool(event.is_connected)
        status = event.status
        worker_exists = status.get("worker_environment_exists", False)
        manager_state = status.get("manager_state", None)
        self._pb_env_open.setEnabled(
            is_connected and not worker_exists and (manager_state == "idle")
        )
        self._pb_env_close.setEnabled(
            is_connected and worker_exists and (manager_state == "idle")
        )
        self._pb_env_destroy.setEnabled(is_connected and worker_exists)

    def _pb_env_open_clicked(self):
        try:
            self.model.environment_open()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_env_close_clicked(self):
        try:
            self.model.environment_close()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_env_destroy_clicked(self):
        try:
            self.model.environment_destroy()
        except Exception as ex:
            print(f"Exception: {ex}")


class QtReQueueControls(QWidget):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

        self._lb_queue_state = QLabel("STOPPED")

        self._pb_queue_start = QPushButton("Start")
        self._pb_queue_start.setEnabled(False)
        self._pb_queue_start.clicked.connect(self._pb_queue_start_clicked)

        self._pb_queue_stop = QPushButton("Stop")
        self._pb_queue_stop.setEnabled(False)
        self._pb_queue_stop.setCheckable(True)
        self._pb_queue_stop.clicked.connect(self._pb_queue_stop_clicked)

        self._group_box = QGroupBox("Queue")

        vbox = QVBoxLayout()
        vbox.addWidget(self._lb_queue_state, alignment=Qt.AlignHCenter)
        vbox.addWidget(self._pb_queue_start)
        vbox.addWidget(self._pb_queue_stop)

        self._group_box.setLayout(vbox)

        vbox = QVBoxLayout()
        vbox.addWidget(self._group_box)
        self.setLayout(vbox)

        self.model.events.status_changed.connect(self.on_update_widgets)

    def on_update_widgets(self, event):
        # None should be converted to False:
        is_connected = bool(event.is_connected)
        status = event.status
        worker_exists = status.get("worker_environment_exists", False)
        running_item_uid = status.get("running_item_uid", None)
        queue_stop_pending = status.get("queue_stop_pending", False)

        s = "RUNNING" if running_item_uid else "STOPPED"
        self._lb_queue_state.setText(s)

        self._pb_queue_start.setEnabled(
            is_connected and worker_exists and not bool(running_item_uid)
        )
        self._pb_queue_stop.setEnabled(
            is_connected and worker_exists and bool(running_item_uid)
        )
        self._pb_queue_stop.setChecked(queue_stop_pending)

    def _pb_queue_start_clicked(self):
        try:
            self.model.queue_start()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_queue_stop_clicked(self):
        try:
            if self._pb_queue_stop.isChecked():
                print("Stopping the queue")
                self.model.queue_stop()
            else:
                print("Cancelling stop")
                self.model.queue_stop_cancel()
        except Exception as ex:
            print(f"Exception: {ex}")


class QtReExecutionControls(QWidget):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

        self._pb_plan_pause_deferred = QPushButton("Pause: Deferred")
        self._pb_plan_pause_deferred.setEnabled(False)
        self._pb_plan_pause_deferred.clicked.connect(
            self._pb_plan_pause_deferred_clicked
        )

        self._pb_plan_pause_immediate = QPushButton("Pause: Immediate")
        self._pb_plan_pause_immediate.setEnabled(False)
        self._pb_plan_pause_immediate.clicked.connect(
            self._pb_plan_pause_immediate_clicked
        )

        self._pb_plan_resume = QPushButton("Resume")
        self._pb_plan_resume.setEnabled(False)
        self._pb_plan_resume.clicked.connect(self._pb_plan_resume_clicked)

        self._pb_plan_stop = QPushButton("Stop")
        self._pb_plan_stop.setEnabled(False)
        self._pb_plan_stop.clicked.connect(self._pb_plan_stop_clicked)

        self._pb_plan_abort = QPushButton("Abort")
        self._pb_plan_abort.setEnabled(False)
        self._pb_plan_abort.clicked.connect(self._pb_plan_abort_clicked)

        self._pb_plan_halt = QPushButton("Halt")
        self._pb_plan_halt.setEnabled(False)
        self._pb_plan_halt.clicked.connect(self._pb_plan_halt_clicked)

        self._group_box = QGroupBox("Plan Execution")

        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addWidget(self._pb_plan_pause_deferred)
        hbox.addWidget(self._pb_plan_pause_immediate)
        vbox.addLayout(hbox)
        vbox.addWidget(self._pb_plan_resume)
        hbox = QHBoxLayout()
        hbox.addWidget(self._pb_plan_stop)
        hbox.addWidget(self._pb_plan_abort)
        hbox.addWidget(self._pb_plan_halt)
        vbox.addLayout(hbox)
        self._group_box.setLayout(vbox)

        vbox = QVBoxLayout()
        vbox.addWidget(self._group_box)
        self.setLayout(vbox)

        self.model.events.status_changed.connect(self.on_update_widgets)

    def on_update_widgets(self, event):
        # None should be converted to False:
        is_connected = bool(event.is_connected)
        status = event.status
        worker_exists = status.get("worker_environment_exists", False)
        manager_state = status.get("manager_state", None)
        self._pb_plan_pause_deferred.setEnabled(
            is_connected and worker_exists and (manager_state == "executing_queue")
        )
        self._pb_plan_pause_immediate.setEnabled(
            is_connected and worker_exists and (manager_state == "executing_queue")
        )
        self._pb_plan_resume.setEnabled(
            is_connected and worker_exists and (manager_state == "paused")
        )
        self._pb_plan_stop.setEnabled(
            is_connected and worker_exists and (manager_state == "paused")
        )
        self._pb_plan_abort.setEnabled(
            is_connected and worker_exists and (manager_state == "paused")
        )
        self._pb_plan_halt.setEnabled(
            is_connected and worker_exists and (manager_state == "paused")
        )

    def _pb_plan_pause_deferred_clicked(self):
        try:
            self.model.re_pause(option="deferred")
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_plan_pause_immediate_clicked(self):
        try:
            self.model.re_pause(option="immediate")
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_plan_resume_clicked(self):
        try:
            self.model.re_resume()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_plan_stop_clicked(self):
        try:
            self.model.re_stop()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_plan_abort_clicked(self):
        try:
            self.model.re_abort()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_plan_halt_clicked(self):
        try:
            self.model.re_halt()
        except Exception as ex:
            print(f"Exception: {ex}")


class QtReStatusMonitor(QWidget):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

        self._lb_environment_exists_text = "RE Environment: "
        self._lb_manager_state_text = "RE Manager state: "
        self._lb_items_in_history_text = "Items in history: "
        self._lb_queue_is_running_text = "Queue is running: "
        self._lb_queue_stop_pending_text = "Queue STOP pending: "
        self._lb_items_in_queue_text = "Items in queue: "

        self._lb_environment_exists = QLabel(self._lb_environment_exists_text + "-")
        self._lb_manager_state = QLabel(self._lb_manager_state_text + "-")
        self._lb_items_in_history = QLabel(self._lb_items_in_history_text + "-")
        self._lb_queue_is_running = QLabel(self._lb_queue_is_running_text + "-")
        self._lb_queue_stop_pending = QLabel(self._lb_queue_stop_pending_text + "-")
        self._lb_items_in_queue = QLabel(self._lb_items_in_queue_text + "-")

        self._group_box = QGroupBox("RE Manager Status")

        hbox = QHBoxLayout()

        vbox = QVBoxLayout()
        vbox.addWidget(self._lb_environment_exists)
        vbox.addWidget(self._lb_manager_state)
        vbox.addWidget(self._lb_items_in_history)
        hbox.addLayout(vbox)

        hbox.addSpacing(10)

        vbox = QVBoxLayout()
        vbox.addWidget(self._lb_queue_is_running)
        vbox.addWidget(self._lb_queue_stop_pending)
        vbox.addWidget(self._lb_items_in_queue)
        hbox.addLayout(vbox)

        self._group_box.setLayout(hbox)

        vbox = QVBoxLayout()
        vbox.addWidget(self._group_box)
        self.setLayout(vbox)

        self.model.events.status_changed.connect(self.on_update_widgets)

    def _set_label_text(self, label, prefix, value):
        if value is None:
            value = "-"
        label.setText(f"{prefix}{value}")

    def on_update_widgets(self, event):
        status = event.status
        worker_exists = status.get("worker_environment_exists", None)
        manager_state = status.get("manager_state", None)
        items_in_history = status.get("items_in_history", None)
        items_in_queue = status.get("items_in_queue", None)
        queue_is_running = bool(status.get("running_item_uid", False))
        queue_stop_pending = status.get("queue_stop_pending", None)

        # Capitalize state of RE Manager
        manager_state = (
            manager_state.upper() if isinstance(manager_state, str) else manager_state
        )

        self._set_label_text(
            self._lb_environment_exists,
            self._lb_environment_exists_text,
            "OPEN" if worker_exists else "CLOSED",
        )
        self._set_label_text(
            self._lb_manager_state, self._lb_manager_state_text, manager_state
        )
        self._set_label_text(
            self._lb_items_in_history,
            self._lb_items_in_history_text,
            str(items_in_history),
        )
        self._set_label_text(
            self._lb_items_in_queue, self._lb_items_in_queue_text, str(items_in_queue)
        )
        self._set_label_text(
            self._lb_queue_is_running,
            self._lb_queue_is_running_text,
            "YES" if queue_is_running else "NO",
        )
        self._set_label_text(
            self._lb_queue_stop_pending,
            self._lb_queue_stop_pending_text,
            "YES" if queue_stop_pending else "NO",
        )


# class QtPlanQueue(QListWidget):
#     def __init__(self, model, parent=None):
#         super().__init__(parent)
#         self.model = model
#
#         for item in self.model:
#             self.addItem(repr(item))
#
#         self.model.events.added.connect(self._on_item_added)
#         self.model.events.removed.connect(self._on_item_removed)
#
#     def _on_item_added(self, event):
#         self.insertItem(event.index, repr(event.item))
#
#     def _on_item_removed(self, event):
#         widget = self.item(event.index)
#         self.removeItemWidget(widget)
