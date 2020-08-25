import time
from datetime import timedelta
from qtpy.QtCore import QDateTime
from qtpy.QtWidgets import (
    QButtonGroup,
    QDateTimeEdit,
    QWidget,
    QPushButton,
    QFormLayout,
    QRadioButton,
    QGridLayout,
)
from ..components.search.search_input import SearchInput

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
        self.today_widget = QRadioButton("Last 24h")
        self.hour_widget = QRadioButton("Last 1 Hour")
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

        # Restrict acceptable timedelta values
        self.allowed = {timedelta(days=1), timedelta(days=30), timedelta(minutes=60)}
        def time_validator(since=None, until=None):
            """
            Enforce that since and until are values that a UI can represent.
            This is an example similar to what will be used in the Qt UI.
            """
            now = timedelta()
            if isinstance(since, timedelta):
                if not (until is None or until == now):
                    raise ValueError(
                        "This UI cannot express since=timedelta(...) unless until "
                        "is timedelta() or None."
                    )
                for item in allowed:
                    if since == item:
                        break
                else:
                    # No matches
                    raise ValueError(
                        "This UI can only express since as a timedelta if it is "
                        f"one of {allowed}. The value {since} is not allowed"
                    )
        s = SearchInput()
        s.time_validator = time_validator

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

        # Refresh Button
        self.refresh_button = QPushButton("Refresh")
        self.layout().addWidget(self.refresh_button)

        # Initialize values.
        qdatetime = QDateTime()
        qdatetime.setSecsSinceEpoch(self.model.since.timestamp())
        self.since_widget.setDateTime(qdatetime)
        qdatetime = QDateTime()
        qdatetime.setSecsSinceEpoch(self.model.until.timestamp())
        self.until_widget.setDateTime(qdatetime)

        # Changes to the GUI update the model.
        self.since_widget.dateTimeChanged.connect(self.on_since_view_changed)
        self.until_widget.dateTimeChanged.connect(self.on_until_view_changed)
        # TODO: check what refresh button is doing
        self.refresh_button.clicked.connect(self.model.request_reload)
        # self.refresh_button.clicked.connect(self.on_refresh_clicked)
        # Changes to the model update the GUI.
        self.model.events.since.connect(self.on_since_model_changed)
        self.model.events.until.connect(self.on_until_model_changed)

        # connect QRadioButtons and change date dropdowns (since/until widgets) accordingly
        self.today_widget.clicked.connect(self.on_select_today)
        self.hour_widget.clicked.connect(self.on_select_lasthour)
        self.days_widget.clicked.connect(self.on_select_30days)
        self.all_widget.clicked.connect(self.on_select_all)

    def on_reload(self):
        now = time.time()
        if isinstance(self.model.since, timedelta):
            self.since_widget.setDateTime(
                QDateTime.fromSecsSinceEpoch(now + self.model.since.total_seconds()))
        if isinstance(self.model.until, timedelta):
            self.until_widget.setDateTime(
                QDateTime.fromSecsSinceEpoch(now + self.model.until.total_seconds()))

        # TODO: since/until widget should update immediately when clicking refresh
        # TODO: check which RButton is selected to update that range

    def on_since_view_changed(self, qdatetime):
        # When GUI is updated
        self.model.since = qdatetime.toSecsSinceEpoch()

    def on_since_model_changed(self, event):
        # When model is updated (e.g. from console or by clicking a QRadioButton)
        now = time.time()
        if isinstance(event.date, timedelta):
            if event.date == timedelta(days=-1):
                self.since_widget.setDateTime(
                    QDateTime.fromSecsSinceEpoch(now + event.date.total_seconds()))
                self.until_widget.setDateTime(QDateTime.fromSecsSinceEpoch(now))
                self.today_widget.setChecked(True)
            if event.date == timedelta(days=-30):
                self.since_widget.setDateTime(
                    QDateTime.fromSecsSinceEpoch(now + event.date.total_seconds()))
                self.until_widget.setDateTime(QDateTime.fromSecsSinceEpoch(now))
                self.days_widget.setChecked(True)
            if event.date == timedelta(minutes=-60):
                self.since_widget.setDateTime(
                    QDateTime.fromSecsSinceEpoch(now + event.date.total_seconds()))
                self.until_widget.setDateTime(QDateTime.fromSecsSinceEpoch(now))
                self.hour_widget.setChecked(True)
            if event.date == timedelta(seconds=-4861699200):
                self.since_widget.setDateTime(
                    QDateTime.fromSecsSinceEpoch(event.date.total_seconds()))
                self.until_widget.setDateTime(QDateTime.fromSecsSinceEpoch(now))
                self.all_widget.setChecked(True)
        else:
            qdatetime = QDateTime()
            qdatetime.setSecsSinceEpoch(event.date.timestamp())
            self.since_widget.setDateTime(qdatetime)
            self.uncheck_radiobuttons
            # does a reload make sense?
            self.model.request_reload()

    def on_until_view_changed(self, qdatetime):
        # When GUI is updated
        self.model.until = qdatetime.toSecsSinceEpoch()

    def on_until_model_changed(self, event):
        # When model is updated (e.g. from console)
        if not isinstance(event.date, timedelta):
            qdatetime = QDateTime()
            qdatetime.setSecsSinceEpoch(event.date.timestamp())
            self.until_widget.setDateTime(qdatetime)
            self.uncheck_radiobuttons
            self.model.request_reload()

    def on_select_today(self):
        self.model.since = timedelta(days=-1)
        self.model.until = timedelta()

    def on_select_lasthour(self):
        self.model.since = timedelta(minutes=-60)
        self.model.until = timedelta()

    def on_select_30days(self):
        self.model.since = timedelta(days=-30)
        self.model.until = timedelta()

    def on_select_all(self):
        self.model.since = timedelta(seconds=-4861699200)
        self.model.until = timedelta()
        # TODO: Add print command to see what Scientist's birthday was set as since date
        # we could have a set to choose from randomly ;-)

    def uncheck_radiobuttons(self):
        self.radio_button_group.setExclusive(False)
        self.all_widget.setChecked(False)
        self.days_widget.setChecked(False)
        self.today_widget.setChecked(False)
        self.hour_widget.setChecked(False)
        self.radio_button_group.setExclusive(True)
