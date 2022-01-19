"""
Extendeding and supplementing the widgets import bluesky-widgets
"""
from bluesky_widgets.qt.run_engine_client import (
    QtReEnvironmentControls,
    QtReManagerConnection,
    QtReQueueControls,
    QtReExecutionControls,
    QtReStatusMonitor,
    QtRePlanQueue,
    QtRePlanHistory,
    QtReRunningPlan,
    QtRePlanEditor,
    QtReConsoleMonitor,
)
from qtpy.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QTabWidget,
    QFrame,
    QSplitter,
)
from qtpy.QtCore import Qt


class QtOrganizeQueueWidgets(QSplitter):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model

        self.setOrientation(Qt.Vertical)

        self._frame_1 = QFrame(self)
        self._frame_2 = QFrame(self)
        self._frame_3 = QFrame(self)
        self._frame_4 = QFrame(self)

        self.addWidget(self._frame_1)
        self.addWidget(self._frame_2)
        self.addWidget(self._frame_3)
        self.addWidget(self._frame_4)

        self._running_plan = QtReRunningPlan(model)
        self._running_plan.monitor_mode = True
        self._plan_queue = QtRePlanQueue(model)
        self._plan_queue.monitor_mode = True
        self._plan_history = QtRePlanHistory(model)
        self._plan_history.monitor_mode = True
        self._console_monitor = QtReConsoleMonitor(model)

        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(self._running_plan)
        self._frame_1.setLayout(vbox)

        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(self._plan_queue)
        self._frame_2.setLayout(vbox)

        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(self._plan_history)
        self._frame_3.setLayout(vbox)

        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(self._console_monitor)
        self._frame_4.setLayout(vbox)

        h = self.sizeHint().height()
        self.setSizes([h, 2 * h, 2 * h, h])


class QtRunEngineManager_Monitor(QWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addWidget(QtReManagerConnection(model))
        hbox.addWidget(QtReStatusMonitor(model))
        hbox.addStretch()
        vbox.addLayout(hbox)

        vbox.addWidget(QtOrganizeQueueWidgets(model), stretch=2)

        self.setLayout(vbox)


class QtRunEngineManager_Editor(QWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addWidget(QtReEnvironmentControls(model))
        hbox.addWidget(QtReQueueControls(model))
        hbox.addWidget(QtReExecutionControls(model))
        hbox.addWidget(QtReStatusMonitor(model))

        hbox.addStretch()
        vbox.addLayout(hbox)

        hbox = QHBoxLayout()
        vbox1 = QVBoxLayout()

        # Register plan editor (opening plans in the editor by double-clicking the plan in the table)
        pe = QtRePlanEditor(model)
        pq = QtRePlanQueue(model)
        pq.registered_item_editors.append(pe.edit_queue_item)

        vbox1.addWidget(pe, stretch=1)
        vbox1.addWidget(pq, stretch=1)
        hbox.addLayout(vbox1)
        vbox2 = QVBoxLayout()
        vbox2.addWidget(QtReRunningPlan(model), stretch=1)
        vbox2.addWidget(QtRePlanHistory(model), stretch=2)
        hbox.addLayout(vbox2)
        vbox.addLayout(hbox)
        self.setLayout(vbox)


class QtViewer(QTabWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model

        self.setTabPosition(QTabWidget.West)

        self._re_manager_monitor = QtRunEngineManager_Monitor(model.run_engine)
        self.addTab(self._re_manager_monitor, "Monitor Queue")

        self._re_manager_editor = QtRunEngineManager_Editor(model.run_engine)
        self.addTab(self._re_manager_editor, "Edit and Control Queue")
