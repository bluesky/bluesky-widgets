import time

from qtpy.QtWidgets import (
    QWidget,
    QListWidget,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
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
        self.model.events.status_changed.connect(self.on_update_online_indicator)

    def _update_widget_states(self):
        self._pb_re_manager_connect.setEnabled(not self.updates_activated)
        self._pb_re_manager_disconnect.setEnabled(self.updates_activated)
        self._lb_connected.setText(
            "-----"
        )  # We don't know if the server is online or offline

    def on_update_online_indicator(self, event):
        text = "-----"
        if self.model.re_manager_accessible is True:
            text = "ONLINE"
        elif self.model.re_manager_accessible is False:
            text = "OFFLINE"
        self._lb_connected.setText(text)

    def _pb_re_manager_connect_clicked(self):
        self.updates_activated = True
        self.model.clear_online_status()
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
            self.model.clear_online_status()
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
        online = bool(
            self.model.re_manager_accessible
        )  # None should be converted to False
        status = self.model.re_manager_status
        worker_exists = status.get("worker_environment_exists", False)
        self._pb_env_open.setEnabled(False)
        self._pb_env_open.setEnabled(online and not worker_exists)
        self._pb_env_close.setEnabled(online and worker_exists)
        self._pb_env_destroy.setEnabled(online and worker_exists)

    def _pb_env_open_clicked(self):
        print("Button clicked: Open environment")
        self.model.environment_open()

    def _pb_env_close_clicked(self):
        print("Button clicked: Close environment")
        self.model.environment_close()

    def _pb_env_destroy_clicked(self):
        print("Button clicked: Destroy environment")
        self.model.environment_destroy()


class QtPlanQueue(QListWidget):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

        for item in self.model:
            self.addItem(repr(item))

        self.model.events.added.connect(self._on_item_added)
        self.model.events.removed.connect(self._on_item_removed)

    def _on_item_added(self, event):
        self.insertItem(event.index, repr(event.item))

    def _on_item_removed(self, event):
        widget = self.item(event.index)
        self.removeItemWidget(widget)
