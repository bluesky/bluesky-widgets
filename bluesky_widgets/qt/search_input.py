import time
from qtpy.QtCore import QDateTime
from qtpy.QtWidgets import (
    QDateTimeEdit,
    QWidget,
    QPushButton,
    QFormLayout,
    QRadioButton,
    QGridLayout,
    QButtonGroup
)


class QtSearchInput(QWidget):
    """
    Qt view for SearchInput

    Parameters
    ----------
    model: SearchInput
    """

    def __init__(self, model, *args, **kwargs):
        self.model = model
        super().__init__(*args, **kwargs)

        self.setLayout(QFormLayout())
        # 4 Radiobuttons to quickly select default time period
        self.all_widget = QRadioButton("All")
        self.days_widget = QRadioButton("30 Days")
        self.today_widget = QRadioButton("Today")
        self.hour_widget = QRadioButton("Last Hour")
        self.radio_button_group = QButtonGroup()
        self.radio_button_group.addButton(self.all_widget)
        self.radio_button_group.addButton(self.days_widget)
        self.radio_button_group.addButton(self.today_widget)
        self.radio_button_group.addButton(self.hour_widget)
        default_period_layout = QGridLayout()
        default_period_layout.addWidget(self.all_widget, 0, 0, 1, 1)
        default_period_layout.addWidget(self.days_widget, 0, 1, 1, 1)
        default_period_layout.addWidget(self.today_widget, 1, 0, 1, 1)
        default_period_layout.addWidget(self.hour_widget, 1, 1, 1, 1)
        self.layout().addRow("When:", default_period_layout)

        # "Since: <datetime picker>"
        self.since_widget = QDateTimeEdit()
        self.since_widget.setCalendarPopup(True)
        self.since_widget.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.layout().addRow("Since:", self.since_widget)
        self.since_widget.dateTimeChanged.connect(self.uncheck_radiobuttons)

        # "Until: <datetime picker>"
        self.until_widget = QDateTimeEdit()
        self.until_widget.setCalendarPopup(True)
        self.until_widget.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.layout().addRow("Until:", self.until_widget)
        self.until_widget.dateTimeChanged.connect(self.uncheck_radiobuttons)

        self.refresh_button = QPushButton("Refresh")
        self.layout().addWidget(self.refresh_button)

        # Initialize values.
        qdatetime = QDateTime()
        qdatetime.setSecsSinceEpoch(self.model.since)
        self.since_widget.setDateTime(qdatetime)
        qdatetime = QDateTime()
        qdatetime.setSecsSinceEpoch(self.model.until)
        self.until_widget.setDateTime(qdatetime)

        # Changes to the GUI update the model.
        self.since_widget.dateTimeChanged.connect(self.on_since_view_changed)
        self.until_widget.dateTimeChanged.connect(self.on_until_view_changed)
        self.refresh_button.clicked.connect(self.model.events.reload)
        self.refresh_button.clicked.connect(self.on_refresh_clicked)
        # Changes to the model update the GUI.
        self.model.events.since.connect(self.on_since_model_changed)
        self.model.events.until.connect(self.on_until_model_changed)

        # connect QRadioButtons and change date dropdowns (since/until widgets) accordingly
        self.today_widget.clicked.connect(self.on_select_today)
        self.hour_widget.clicked.connect(self.on_select_lasthour)
        self.days_widget.clicked.connect(self.on_select_30days)
        self.all_widget.clicked.connect(self.on_select_all)

        self.now = time.time()
        self.ONE_HOUR = 60 * 60
        self.TODAY = self.ONE_HOUR * 24
        self.ONE_WEEK = self.TODAY * 7
        self.ONE_MONTH = self.TODAY * 30 #used for 30 days QRadioButton

    def on_since_view_changed(self, qdatetime):
        # When GUI is updated
        self.model.since = qdatetime.toSecsSinceEpoch()

    def on_since_model_changed(self, event):
        # When model is updated (e.g. from console)
        qdatetime = QDateTime()
        qdatetime.setSecsSinceEpoch(event.date)
        self.since_widget.setDateTime(qdatetime)

    def on_until_view_changed(self, qdatetime):
        # When GUI is updated
        self.model.until = qdatetime.toSecsSinceEpoch()

    def on_until_model_changed(self, event):
        # When model is updated (e.g. from console)
        qdatetime = QDateTime()
        qdatetime.setSecsSinceEpoch(event.date)
        self.until_widget.setDateTime(qdatetime)

    def on_refresh_clicked(self):
        self.now = time.time()
        #TODO: since/until widget should update immediately when clicking refresh
        # check which RButton is selected to update that range

    def set_timerange(self, timerange):
        self.since_widget.setDateTime(QDateTime.fromSecsSinceEpoch(self.now - timerange))
        self.until_widget.setDateTime(QDateTime.fromSecsSinceEpoch(self.now))

    def on_select_today(self):
        self.set_timerange(self.TODAY)
        self.today_widget.setChecked(True)

    def on_select_lasthour(self):
        self.set_timerange(self.ONE_HOUR)
        self.hour_widget.setChecked(True)

    def on_select_30days(self):
        self.set_timerange(self.ONE_MONTH)
        self.days_widget.setChecked(True)

    def on_select_all(self):
        self.model.until = None
        self.model.since = None
        self.since_widget.setDateTime(QDateTime.fromSecsSinceEpoch(0))
        self.until_widget.setDateTime(QDateTime.fromSecsSinceEpoch(self.now))
        self.all_widget.setChecked(True)

    def uncheck_radiobuttons(self):
        self.radio_button_group.setExclusive(False)
        self.all_widget.setChecked(False)
        self.days_widget.setChecked(False)
        self.today_widget.setChecked(False)
        self.hour_widget.setChecked(False)
        self.radio_button_group.setExclusive(True)
