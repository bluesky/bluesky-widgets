import time
import pprint

from qtpy.QtWidgets import (
    QWidget,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QTextEdit,
)
from qtpy.QtCore import Qt, Signal, Slot, QTimer
from qtpy.QtGui import QFontMetrics, QPalette

from bluesky_widgets.qt.threading import FunctionWorker


class QtReManagerConnection(QWidget):
    signal_update_widget = Signal(object)

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
        self.signal_update_widget.connect(self.slot_update_widgets)

    def _update_widget_states(self):
        self._pb_re_manager_connect.setEnabled(not self.updates_activated)
        self._pb_re_manager_disconnect.setEnabled(self.updates_activated)

        # We don't know if the server is online or offline:
        self._lb_connected.setText("-----")

    def on_update_widgets(self, event):
        is_connected = event.is_connected
        self.signal_update_widget.emit(is_connected)

    @Slot(object)
    def slot_update_widgets(self, is_connected):
        # 'is_connected' may take values None, True and False
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
        self.model.manager_connecting_ops()
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
    signal_update_widget = Signal(bool, object)

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
        self.signal_update_widget.connect(self.slot_update_widgets)

    def on_update_widgets(self, event):
        is_connected = bool(event.is_connected)
        status = event.status
        self.signal_update_widget.emit(is_connected, status)

    @Slot(bool, object)
    def slot_update_widgets(self, is_connected, status):
        # 'is_connected' takes values True, False
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
    signal_update_widget = Signal(bool, object)

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
        self.signal_update_widget.connect(self.slot_update_widgets)

    def on_update_widgets(self, event):
        is_connected = bool(event.is_connected)
        status = event.status
        self.signal_update_widget.emit(is_connected, status)

    @Slot(bool, object)
    def slot_update_widgets(self, is_connected, status):
        # 'is_connected' takes values True, False
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
                self.model.queue_stop()
            else:
                self.model.queue_stop_cancel()
        except Exception as ex:
            print(f"Exception: {ex}")


class QtReExecutionControls(QWidget):
    signal_update_widget = Signal(bool, object)

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
        self.signal_update_widget.connect(self.slot_update_widgets)

    def on_update_widgets(self, event):
        is_connected = bool(event.is_connected)
        status = event.status
        self.signal_update_widget.emit(is_connected, status)

    @Slot(bool, object)
    def slot_update_widgets(self, is_connected, status):
        # 'is_connected' takes values True, False
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
    signal_update_widget = Signal(object)

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
        self.signal_update_widget.connect(self.slot_update_widgets)

    def _set_label_text(self, label, prefix, value):
        if value is None:
            value = "-"
        label.setText(f"{prefix}{value}")

    def on_update_widgets(self, event):
        status = event.status
        self.signal_update_widget.emit(status)

    @Slot(object)
    def slot_update_widgets(self, status):
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


class QueueTableWidget(QTableWidget):
    signal_drop_event = Signal(int, int)
    signal_scroll = Signal(str)
    signal_resized = Signal()

    def __init__(self):
        super().__init__()
        self._is_mouse_pressed = False
        self._is_scroll_active = False
        self._scroll_direction = ""

        self._scroll_timer_count = 0
        # Duration of period of the first series of events, ms
        self._scroll_timer_period_1 = 200
        # Duration of period of the remaining events, ms
        self._scroll_timer_period_2 = 100
        self._scroll_timer_n_events = 4  # The number of events in the first period
        self._scroll_timer = QTimer()
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._on_scroll_timeout)

    def dropEvent(self, event):
        self.deactivate_scroll()
        row, col = -1, -1
        if (event.source() == self) and self.viewport().rect().contains(event.pos()):
            index = self.indexAt(event.pos())
            if not index.isValid() or not self.visualRect(index).contains(event.pos()):
                index = self.rootIndex()
            row = index.row()
            col = index.column()

        self.signal_drop_event.emit(row, col)

    def dragMoveEvent(self, event):
        # 'rowHeight(0)' will return 0 if the table is empty,
        #    but we don't need to scroll the empty table
        scroll_activation_area = int(self.rowHeight(0) / 2)

        y = event.pos().y()
        if y < scroll_activation_area:
            self.activate_scroll("up")
        elif y > self.viewport().height() - scroll_activation_area:
            self.activate_scroll("down")
        else:
            self.deactivate_scroll()

    def dragLeaveEvent(self, event):
        self.deactivate_scroll()

    def activate_scroll(self, str):
        if str not in ("up", "down"):
            return

        if not self._is_scroll_active or self._scroll_direction != str:
            self._is_scroll_active = True
            self._scroll_direction = str
            self._scroll_timer_count = 0
            # The period before the first scroll event should be very short
            self._scroll_timer.start(20)

    def deactivate_scroll(self):
        if self._is_scroll_active:
            self._is_scroll_active = False
            self._scroll_direction = ""
            self._scroll_timer.stop()

    def _on_scroll_timeout(self):
        self.signal_scroll.emit(self._scroll_direction)

        self._scroll_timer_count += 1
        timeout = (
            self._scroll_timer_period_1
            if self._scroll_timer_count <= self._scroll_timer_n_events
            else self._scroll_timer_period_2
        )
        self._scroll_timer.start(timeout)


class PushButtonMinimumWidth(QPushButton):
    """
    Push button minimum width necessary to fit the text
    """

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        text = self.text()
        font = self.font()

        fm = QFontMetrics(font)
        text_width = fm.width(text) + 6
        self.setFixedWidth(text_width)


class QtRePlanQueue(QWidget):

    signal_update_widgets = Signal(bool)
    signal_update_selection = Signal(str)
    signal_plan_queue_changed = Signal(object, str)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

        self._table_column_labels = (
            "",
            "Name",
            "Args",
            "Parameters",
            "USER",
            "GROUP",
        )
        self._table = QueueTableWidget()
        self._table.setColumnCount(len(self._table_column_labels))
        # self._table.verticalHeader().hide()
        self._table.setHorizontalHeaderLabels(self._table_column_labels)
        self._table.horizontalHeader().setSectionsMovable(True)

        self._table.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)

        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setDragEnabled(False)
        self._table.setAcceptDrops(False)
        self._table.setDropIndicatorShown(True)
        self._table.setShowGrid(True)

        self._table.setAlternatingRowColors(True)

        self._table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setMinimumSectionSize(5)

        self._table_scrolled_to_bottom = False

        # The following parameters are used only to control widget state (e.g. activate/deactivate
        #   buttons), not to perform real operations.
        self._n_table_items = 0  # The number of items in the table
        self._n_selected_item = -1  # Selected item (table row)

        self._pb_move_up = PushButtonMinimumWidth("Move Up")
        self._pb_move_down = PushButtonMinimumWidth("Down")
        self._pb_move_to_top = PushButtonMinimumWidth("Top")
        self._pb_move_to_bottom = PushButtonMinimumWidth("Bottom")
        self._pb_delete_plan = PushButtonMinimumWidth("Delete")
        self._pb_duplicate_plan = PushButtonMinimumWidth("Duplicate")
        self._pb_clear_queue = PushButtonMinimumWidth("Clear")
        self._pb_deselect = PushButtonMinimumWidth("Deselect")

        self._pb_move_up.clicked.connect(self._pb_move_up_clicked)
        self._pb_move_down.clicked.connect(self._pb_move_down_clicked)
        self._pb_move_to_top.clicked.connect(self._pb_move_to_top_clicked)
        self._pb_move_to_bottom.clicked.connect(self._pb_move_to_bottom_clicked)
        self._pb_delete_plan.clicked.connect(self._pb_delete_plan_clicked)
        self._pb_duplicate_plan.clicked.connect(self._pb_duplicate_plan_clicked)
        self._pb_clear_queue.clicked.connect(self._pb_clear_queue_clicked)
        self._pb_deselect.clicked.connect(self._pb_deselect_clicked)

        self._group_box = QGroupBox("Plan Queue")
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("QUEUE"))
        hbox.addStretch(1)
        hbox.addWidget(self._pb_move_up)
        hbox.addWidget(self._pb_move_down)
        hbox.addWidget(self._pb_move_to_top)
        hbox.addWidget(self._pb_move_to_bottom)
        hbox.addStretch(2)
        hbox.addWidget(self._pb_deselect)
        hbox.addWidget(self._pb_clear_queue)
        hbox.addStretch(1)
        hbox.addWidget(self._pb_delete_plan)
        hbox.addWidget(self._pb_duplicate_plan)
        vbox.addLayout(hbox)
        vbox.addWidget(self._table)
        self.setLayout(vbox)

        self.model.events.status_changed.connect(self.on_update_widgets)
        self.signal_update_widgets.connect(self.slot_update_widgets)

        self.model.events.plan_queue_changed.connect(self.on_plan_queue_changed)
        self.signal_plan_queue_changed.connect(self.slot_plan_queue_changed)

        self.model.events.queue_item_selection_changed.connect(
            self.on_queue_item_selection_changed
        )
        self.signal_update_selection.connect(self.slot_change_selection)

        self._table.signal_drop_event.connect(self.on_table_drop_event)
        self._table.signal_scroll.connect(self.on_table_scroll_event)

        self._table.itemSelectionChanged.connect(self.on_item_selection_changed)
        self._table.verticalScrollBar().valueChanged.connect(
            self.on_vertical_scrollbar_value_changed
        )
        self._table.verticalScrollBar().rangeChanged.connect(
            self.on_vertical_scrollbar_range_changed
        )

        self._update_button_states()

    def on_update_widgets(self, event):
        # None should be converted to False:
        is_connected = bool(event.is_connected)
        self.signal_update_widgets.emit(is_connected)

    @Slot(bool)
    def slot_update_widgets(self, is_connected):
        # Disable drops if there is no connection to RE Manager
        self._table.setDragEnabled(is_connected)
        self._table.setAcceptDrops(is_connected)

        self._update_button_states()

    def _update_button_states(self):
        is_connected = bool(self.model.re_manager_connected)
        n_items = self._n_table_items
        n_selected_item = self._n_selected_item

        is_sel = n_selected_item >= 0
        sel_top = n_selected_item == 0
        sel_bottom = n_selected_item == n_items - 1

        self._pb_move_up.setEnabled(is_connected and is_sel and not sel_top)
        self._pb_move_down.setEnabled(is_connected and is_sel and not sel_bottom)
        self._pb_move_to_top.setEnabled(is_connected and is_sel and not sel_top)
        self._pb_move_to_bottom.setEnabled(is_connected and is_sel and not sel_bottom)

        self._pb_clear_queue.setEnabled(is_connected and n_items)

        self._pb_delete_plan.setEnabled(is_connected and is_sel)
        self._pb_duplicate_plan.setEnabled(is_connected and is_sel)

    def on_vertical_scrollbar_value_changed(self, value):
        max = self._table.verticalScrollBar().maximum()
        self._table_scrolled_to_bottom = value == max

    def on_vertical_scrollbar_range_changed(self, min, max):
        if self._table_scrolled_to_bottom:
            self._table.verticalScrollBar().setValue(max)

    def on_table_drop_event(self, row, col):
        # If the selected queue item is not in the table anymore (e.g. sent to execution),
        #   then ignore the drop event, since the item can not be moved.
        if self.model.selected_queue_item_uid:
            item_uid_to_replace = self.model.queue_item_pos_to_uid(row)
            try:
                self.model.queue_item_move_in_place_of(item_uid_to_replace)
            except Exception as ex:
                print(f"Exception: {ex}")

        self._update_button_states()

    def on_table_scroll_event(self, scroll_direction):
        v = self._table.verticalScrollBar().value()
        v_max = self._table.verticalScrollBar().maximum()
        if scroll_direction == "up" and v > 0:
            v_new = v - 1
        elif scroll_direction == "down" and v < v_max:
            v_new = v + 1
        else:
            v_new = v
        if v != v_new:
            self._table.verticalScrollBar().setValue(v_new)

    def on_plan_queue_changed(self, event):
        plan_queue_items = event.plan_queue_items
        selected_item_uid = event.selected_item_uid
        self.signal_plan_queue_changed.emit(plan_queue_items, selected_item_uid)

    @Slot(object, str)
    def slot_plan_queue_changed(self, plan_queue_items, selected_item_uid):

        # Check if the vertical scroll bar is scrolled to the bottom. Ignore the case
        #   when 'scroll_value==0': if the top plan is visible, it should remain visible
        #   even if additional plans are added to the queue.
        scroll_value = self._table.verticalScrollBar().value()
        scroll_maximum = self._table.verticalScrollBar().maximum()
        self._table_scrolled_to_bottom = scroll_value and (
            scroll_value == scroll_maximum
        )

        self._table.clearContents()
        self._table.setRowCount(len(plan_queue_items))

        if len(plan_queue_items):
            resize_mode = QHeaderView.ResizeToContents
        else:
            # Empty table, stretch the header
            resize_mode = QHeaderView.Stretch
        self._table.horizontalHeader().setSectionResizeMode(resize_mode)

        for nr, item in enumerate(plan_queue_items):
            for nc, col_name in enumerate(self._table_column_labels):
                try:
                    value = self.model.get_item_value_for_label(
                        item=item, label=col_name
                    )
                except KeyError:
                    value = ""
                table_item = QTableWidgetItem(value)
                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                self._table.setItem(nr, nc, table_item)

        # Update the number of table items
        self._n_table_items = len(plan_queue_items)

        # Advance scrollbar if the table is scrolled all the way down.
        if self._table_scrolled_to_bottom:
            scroll_maximum_new = self._table.verticalScrollBar().maximum()
            self._table.verticalScrollBar().setValue(scroll_maximum_new)

        self.slot_change_selection(selected_item_uid)
        self._update_button_states()

    def on_item_selection_changed(self):
        """
        The handler for ``item_selection_changed`` signal emitted by QTableWidget
        """
        sel_rows = self._table.selectionModel().selectedRows()
        # It is assumed that only one row may be selected at a time. If the table settings change
        #   so that more than one row could be selected at a time, the following code will not work.
        try:
            if len(sel_rows) >= 1:
                row = sel_rows[0].row()
                selected_item_uid = self.model.queue_item_pos_to_uid(row)
                self.model.selected_queue_item_uid = selected_item_uid
                self._n_selected_item = row
            else:
                raise Exception()
        except Exception:
            self.model.selected_queue_item_uid = ""
            self._n_selected_item = -1

    def on_queue_item_selection_changed(self, event):
        """
        The handler for the event generated by the model
        """
        selected_item_uid = event.selected_item_uid
        self.signal_update_selection.emit(selected_item_uid)

    @Slot(str)
    def slot_change_selection(self, selected_item_uid):
        row = -1
        if selected_item_uid:
            row = self.model.queue_item_uid_to_pos(selected_item_uid)
        if row < 0:
            self._table.clearSelection()
            self._n_selected_item = -1
        else:
            self._table.selectRow(row)
            self._n_selected_item = row

        self._update_button_states()

    def _pb_move_up_clicked(self):
        try:
            self.model.queue_item_move_up()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_move_down_clicked(self):
        try:
            self.model.queue_item_move_down()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_move_to_top_clicked(self):
        try:
            self.model.queue_item_move_to_top()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_move_to_bottom_clicked(self):
        try:
            self.model.queue_item_move_to_bottom()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_delete_plan_clicked(self):
        try:
            self.model.queue_item_remove()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_clear_queue_clicked(self):
        try:
            self.model.queue_clear()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_deselect_clicked(self):
        self._table.clearSelection()

    def _pb_duplicate_plan_clicked(self):
        try:
            self.model.queue_item_copy_to_queue()
        except Exception as ex:
            print(f"Exception: {ex}")


class QtRePlanHistory(QWidget):
    signal_update_widgets = Signal()
    signal_update_selection = Signal(int)
    signal_plan_history_changed = Signal(object, int)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

        self._table_column_labels = (
            "",
            "Name",
            "STATUS",
            "Args",
            "Parameters",
            "USER",
            "GROUP",
        )
        self._table = QueueTableWidget()
        self._table.setColumnCount(len(self._table_column_labels))
        # self._table.verticalHeader().hide()
        self._table.setHorizontalHeaderLabels(self._table_column_labels)
        self._table.horizontalHeader().setSectionsMovable(True)

        # self._table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._table.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)

        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setShowGrid(True)
        self._table.setAlternatingRowColors(True)

        self._table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setMinimumSectionSize(5)

        self._table_scrolled_to_bottom = False
        # self._table_slider_is_pressed = False

        # The following parameters are used only to control widget state (e.g. activate/deactivate
        #   buttons), not to perform real operations.
        self._n_table_items = 0  # The number of items in the table
        self._n_selected_item = -1  # Selected item (table row)

        self._pb_copy_to_queue = PushButtonMinimumWidth("Copy to Queue")
        self._pb_deselect_all = PushButtonMinimumWidth("Deselect All")
        self._pb_clear_history = PushButtonMinimumWidth("Clear History")

        self._pb_copy_to_queue.clicked.connect(self._pb_copy_to_queue_clicked)
        self._pb_deselect_all.clicked.connect(self._pb_deselect_all_clicked)
        self._pb_clear_history.clicked.connect(self._pb_clear_history_clicked)

        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("HISTORY"))
        hbox.addStretch(1)
        hbox.addWidget(self._pb_copy_to_queue)
        hbox.addStretch(3)
        hbox.addWidget(self._pb_deselect_all)
        hbox.addWidget(self._pb_clear_history)
        vbox.addLayout(hbox)
        vbox.addWidget(self._table)
        self.setLayout(vbox)

        self.model.events.status_changed.connect(self.on_update_widgets)
        self.signal_update_widgets.connect(self.slot_update_widgets)

        self.model.events.plan_history_changed.connect(self.on_plan_history_changed)
        self.signal_plan_history_changed.connect(self.slot_plan_history_changed)

        self.model.events.history_item_selection_changed.connect(
            self.on_history_item_selection_changed
        )
        self.signal_update_selection.connect(self.slot_change_selection)

        self._table.itemSelectionChanged.connect(self.on_item_selection_changed)
        self._table.verticalScrollBar().valueChanged.connect(
            self.on_vertical_scrollbar_value_changed
        )
        self._table.verticalScrollBar().rangeChanged.connect(
            self.on_vertical_scrollbar_range_changed
        )

        self._update_button_states()

    def on_vertical_scrollbar_value_changed(self, value):
        max = self._table.verticalScrollBar().maximum()
        self._table_scrolled_to_bottom = value == max

    def on_vertical_scrollbar_range_changed(self, min, max):
        if self._table_scrolled_to_bottom:
            self._table.verticalScrollBar().setValue(max)

    def on_update_widgets(self, event):
        self.signal_update_widgets.emit()

    @Slot()
    def slot_update_widgets(self):
        self._update_button_states()

    def _update_button_states(self):
        is_connected = bool(self.model.re_manager_connected)
        n_items = self._n_table_items
        n_selected_item = self._n_selected_item

        is_sel = n_selected_item >= 0

        self._pb_copy_to_queue.setEnabled(is_connected and is_sel)
        self._pb_deselect_all.setEnabled(is_sel)
        self._pb_clear_history.setEnabled(is_connected and n_items)

    def on_plan_history_changed(self, event):
        plan_history_items = event.plan_history_items
        selected_item_pos = event.selected_item_pos
        self.signal_plan_history_changed.emit(plan_history_items, selected_item_pos)

    @Slot(object, int)
    def slot_plan_history_changed(self, plan_history_items, selected_item_pos):
        # Check if the vertical scroll bar is scrolled to the bottom.
        scroll_value = self._table.verticalScrollBar().value()
        scroll_maximum = self._table.verticalScrollBar().maximum()
        self._table_scrolled_to_bottom = scroll_value == scroll_maximum

        self._table.clearContents()
        self._table.setRowCount(len(plan_history_items))

        if len(plan_history_items):
            resize_mode = QHeaderView.ResizeToContents
        else:
            # Empty table, stretch the header
            resize_mode = QHeaderView.Stretch
        self._table.horizontalHeader().setSectionResizeMode(resize_mode)

        for nr, item in enumerate(plan_history_items):
            for nc, col_name in enumerate(self._table_column_labels):
                try:
                    value = self.model.get_item_value_for_label(
                        item=item, label=col_name
                    )
                except KeyError:
                    value = ""
                table_item = QTableWidgetItem(value)
                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                self._table.setItem(nr, nc, table_item)

        # Update the number of table items
        self._n_table_items = len(plan_history_items)

        # Advance scrollbar if the table is scrolled all the way down.
        if self._table_scrolled_to_bottom:
            scroll_maximum_new = self._table.verticalScrollBar().maximum()
            self._table.verticalScrollBar().setValue(scroll_maximum_new)

        # Call function directly
        self.slot_change_selection(selected_item_pos)

        self._update_button_states()

    def on_item_selection_changed(self):
        """
        The handler for ``item_selection_changed`` signal emitted by QTableWidget
        """
        sel_rows = self._table.selectionModel().selectedRows()
        # It is assumed that only one row may be selected at a time. If the table settings change
        #   so that more than one row could be selected at a time, the following code will not work.
        try:
            if len(sel_rows) >= 1:
                selected_item_pos = sel_rows[0].row()
                self.model.selected_history_item_pos = selected_item_pos
                self._n_selected_item = selected_item_pos
            else:
                raise Exception()
        except Exception:
            self.model.selected_history_item_pos = -1
            self._n_selected_item = -1

    def on_history_item_selection_changed(self, event):
        """
        The handler for the event generated by the model
        """
        row = event.selected_item_pos
        self.signal_update_selection.emit(row)

    @Slot(int)
    def slot_change_selection(self, selected_item_pos):
        row = selected_item_pos

        if row < 0:
            self._table.clearSelection()
            self._n_selected_item = -1
        else:
            self._table.selectRow(row)
            self._n_selected_item = row

        self._update_button_states()

    def _pb_copy_to_queue_clicked(self):
        try:
            self.model.history_item_add_to_queue()
        except Exception as ex:
            print(f"Exception: {ex}")

    def _pb_deselect_all_clicked(self):
        self._table.clearSelection()
        self._n_selected_item = -1
        self._update_button_states()

    def _pb_clear_history_clicked(self):
        try:
            self.model.history_clear()
        except Exception as ex:
            print(f"Exception: {ex}")


class QtReRunningPlan(QWidget):
    signal_update_widgets = Signal()
    signal_running_item_changed = Signal(object, object)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        # Set background color the same as for disabled window.
        p = self._text_edit.palette()
        p.setColor(QPalette.Base, p.color(QPalette.Disabled, QPalette.Base))
        self._text_edit.setPalette(p)

        self._pb_copy_to_queue = PushButtonMinimumWidth("Copy to Queue")

        self._pb_copy_to_queue.clicked.connect(self._pb_copy_to_queue_clicked)

        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("RUNNING PLAN"))
        hbox.addStretch(1)
        hbox.addWidget(self._pb_copy_to_queue)
        vbox.addLayout(hbox)
        vbox.addWidget(self._text_edit)
        self.setLayout(vbox)

        self._is_item_running = False
        self._running_item_uid = ""
        self._update_button_states()

        self.model.events.running_item_changed.connect(self.on_running_item_changed)
        self.signal_running_item_changed.connect(self.slot_running_item_changed)

        self.model.events.status_changed.connect(self.on_update_widgets)
        self.signal_update_widgets.connect(self.slot_update_widgets)

    def on_running_item_changed(self, event):
        running_item = event.running_item
        run_list = event.run_list
        self.signal_running_item_changed.emit(running_item, run_list)

    @Slot(object, object)
    def slot_running_item_changed(self, running_item, run_list):

        running_item_uid = running_item.get("item_uid", "")
        is_new_item = running_item_uid != self._running_item_uid
        self._running_item_uid = running_item_uid

        s_running_item = ""
        indent = "&nbsp;&nbsp;&nbsp;&nbsp;"

        def _to_html(s):
            """Formats text as a sequence indented html lines"""
            new_line = "<br>" + indent
            return indent + s.replace("\n", new_line)

        if running_item:
            s_running_item += f"<b>Plan Name:</b> {running_item.get('name', '')}<br>"
            if ("args" in running_item) and running_item["args"]:
                s_running_item += (
                    f"<b>Arguments:</b> {str(running_item['args'])[1:-1]}<br>"
                )
            if ("kwargs" in running_item) and running_item["kwargs"]:
                s_running_item += "<b>Parameters:</b><br>"
                for k, v in running_item["kwargs"].items():
                    s_running_item += indent + f"<b>{k}:</b> {v}<br>"

            if ("meta" in running_item) and running_item["meta"]:
                # This representation of metadata may not be the best, but it is still reasonable.
                #   Note, that metadata may be a dictionary or a list of dictionaries.
                s_meta = pprint.pformat(running_item["meta"])
                s_meta = _to_html(s_meta)
                s_running_item += f"<b>Metadata:</b><br>{s_meta}<br>"

        s_run_list = "<b>Runs:</b><br>" if run_list else ""
        for run_info in run_list:
            run_uid = run_info["uid"]
            run_is_open = run_info["is_open"]
            run_exit_status = run_info["exit_status"]
            s_run = indent + f"{run_uid}  "
            if run_is_open:
                s_run += "In progress ..."
            else:
                s_run += f"Exit status: {run_exit_status}"
            s_run_list += s_run + "<br>"

        # The following logic is implemented:
        #   - always scroll to the top of the edit box when the new plan is started.
        #   - don't scroll if contents are changed during execution of a plan unless scroll bar
        #     is all the way down (contents may be changed e.g. during execution of multirun plans)
        #   - if the scroll bar is in the lowest position, then continue scrolling down as text
        #     is added (e.g. UIDs may be added to the list of Run UIDs as multirun plan is executed).
        scroll_value = 0 if is_new_item else self._text_edit.verticalScrollBar().value()
        scroll_maximum = self._text_edit.verticalScrollBar().maximum()
        tb_scrolled_to_bottom = scroll_value and (scroll_value == scroll_maximum)

        self._text_edit.setHtml(s_running_item + s_run_list)

        self._is_item_running = bool(running_item)
        self._update_button_states()

        scroll_maximum_new = self._text_edit.verticalScrollBar().maximum()
        scroll_value_new = scroll_maximum_new if tb_scrolled_to_bottom else scroll_value
        self._text_edit.verticalScrollBar().setValue(scroll_value_new)

    def on_update_widgets(self, event):
        self.signal_update_widgets.emit()

    @Slot()
    def slot_update_widgets(self):
        self._update_button_states()

    def _update_button_states(self):
        is_connected = bool(self.model.re_manager_connected)
        is_plan_running = self._is_item_running

        self._pb_copy_to_queue.setEnabled(is_connected and is_plan_running)

    def _pb_copy_to_queue_clicked(self):
        try:
            self.model.running_item_add_to_queue()
        except Exception as ex:
            print(f"Exception: {ex}")
