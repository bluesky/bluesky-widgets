import contextlib
from datetime import datetime, timedelta
from qtpy.QtCore import QDateTime
from qtpy.QtWidgets import (
    QButtonGroup,
    QDateTimeEdit,
    QWidget,
    QPushButton,
    QFormLayout,
    QRadioButton,
    QGridLayout,
    QLineEdit,
    QHBoxLayout,
    QLabel,
)
from ..models.search import LOCAL_TIMEZONE, secs_since_epoch


def as_qdatetime(datetime):
    "Create QDateTime set as specified by datetime."
    return QDateTime.fromSecsSinceEpoch(
        int(secs_since_epoch(datetime) - datetime.utcoffset() / timedelta(seconds=1))
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
        # Radiobuttons to quickly select default time period
        self.all_widget = QRadioButton("All")
        self.year_widget = QRadioButton("1 Year")
        self.month_widget = QRadioButton("30 Days")
        self.week_widget = QRadioButton("1 Week")
        self.today_widget = QRadioButton("24 Hours")
        self.hour_widget = QRadioButton("1 Hour")
        self.radio_button_group = QButtonGroup()
        self.radio_button_group.addButton(self.all_widget)
        self.radio_button_group.addButton(self.year_widget)
        self.radio_button_group.addButton(self.month_widget)
        self.radio_button_group.addButton(self.week_widget)
        self.radio_button_group.addButton(self.today_widget)
        self.radio_button_group.addButton(self.hour_widget)
        default_period_layout = QGridLayout()
        default_period_layout.setHorizontalSpacing(85)
        default_period_layout.setVerticalSpacing(10)
        default_period_layout.addWidget(self.all_widget, 0, 0, 1, 2)
        default_period_layout.addWidget(self.year_widget, 1, 0, 1, 2)
        default_period_layout.addWidget(self.month_widget, 0, 1, 1, 2)
        default_period_layout.addWidget(self.week_widget, 1, 1, 1, 2)
        default_period_layout.addWidget(self.today_widget, 0, 2, 1, 2)
        default_period_layout.addWidget(self.hour_widget, 1, 2, 1, 2)
        self.layout().addRow("When:", default_period_layout)

        # TODO: rethink if restriction to acceptable timedelta values is required
        # from ..models.search.search_input import SearchInput
        # self.allowed = {timedelta(days=-1), timedelta(days=-30), timedelta(minutes=-60), timedelta(days=-7),
        #                 timedelta(days=-365)}
        # def time_validator(since=None, until=None):
        #     """
        #     Enforce that since and until are values that a UI can represent.
        #     This is an example similar to what will be used in the Qt UI.
        #     """
        #     now = timedelta()
        #     if isinstance(since, timedelta):
        #         if not (until is None or until == now):
        #             raise ValueError(
        #                 "This UI cannot express since=timedelta(...) unless until "
        #                 "is timedelta() or None."
        #             )
        #         for item in allowed:
        #             if since == item:
        #                 break
        #         else:
        #             # No matches
        #             raise ValueError(
        #                 "This UI can only express since as a timedelta if it is "
        #                 f"one of {allowed}. The value {since} is not allowed"
        #             )
        # s = SearchInput()
        # s.time_validator = time_validator

        self.date_selection_row = QHBoxLayout(self)
        self.layout().addRow(self.date_selection_row)

        # "Since: <datetime picker>"
        self.since_widget = QDateTimeEdit()
        self.since_widget.setCalendarPopup(True)
        self.since_widget.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.date_selection_row.addWidget(QLabel("Date range:", self), 0)
        self.date_selection_row.addWidget(self.since_widget, 1)

        # "Until: <datetime picker>"
        self.until_widget = QDateTimeEdit()
        self.until_widget.setCalendarPopup(True)
        self.until_widget.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.date_selection_row.addWidget(QLabel(" \u2013 ", self), 0)
        self.date_selection_row.addWidget(self.until_widget, 1)

        # Field search
        self.field_text_edit = {}
        for field in self.model.fields:
            self.field_text_edit[field] = QLineEdit("")
            self.field_text_edit[field].textChanged.connect(self.on_field_search_view_changed)
            self.model.events.field_search_updated.connect(self.on_field_search_model_changed)
            self.layout().addRow(f"{field}:", self.field_text_edit[field])

        # Text Search
        if model.text_search_supported:
            self.text_search_input = QLineEdit("")
            self.text_search_input.textChanged.connect(self.on_text_view_changed)
            self.model.events.text.connect(self.on_text_model_changed)
            self.layout().addRow("Full Text Search:", self.text_search_input)

        # Refresh Button
        self.refresh_button = QPushButton("Refresh")
        self.layout().addWidget(self.refresh_button)

        # Changes to the GUI update the model.
        self.since_widget.dateTimeChanged.connect(self.on_since_view_changed)
        self.until_widget.dateTimeChanged.connect(self.on_until_view_changed)

        self.refresh_button.clicked.connect(self.model.request_reload)
        self.model.events.reload.connect(self.on_reload)
        self.model.events.query.connect(self.on_reload)
        # Changes to the model update the GUI.
        self.model.events.since.connect(self.on_since_model_changed)
        self.model.events.until.connect(self.on_until_model_changed)

        # connect QRadioButtons and change date dropdowns (since/until widgets) accordingly
        self.hour_widget.toggled.connect(self.on_toggle_hour)
        self.today_widget.toggled.connect(self.on_toggle_24h)
        self.week_widget.toggled.connect(self.on_toggle_week)
        self.month_widget.toggled.connect(self.on_toggle_month)
        self.year_widget.toggled.connect(self.on_toggle_year)
        self.all_widget.toggled.connect(self.on_toggle_all)

        self.all_widget.setChecked(True)

    def on_field_search_view_changed(self, event):
        field_update_dict = {}
        for key, text_edit in self.field_text_edit.items():
            field_update_dict[key] = text_edit.text()
        self.model.field_search.update(field_update_dict)

    def on_field_search_model_changed(self, event):
        for key, text_edit in self.field_text_edit.items():
            text_edit.setText(self.model.field_search[key])

    def on_text_view_changed(self, event):
        self.model.text = self.text_search_input.text()

    def on_text_model_changed(self, event):
        self.text_search_input.setText(event.text)

    def on_reload(self, event):
        now = datetime.now(LOCAL_TIMEZONE)
        if isinstance(self.model.since, timedelta):
            with _blocked(self.since_widget):
                self.since_widget.setDateTime(as_qdatetime(now + self.model.since))
        if isinstance(self.model.until, timedelta):
            with _blocked(self.until_widget):
                self.until_widget.setDateTime(as_qdatetime(now + self.model.until))

    def on_since_view_changed(self, qdatetime):
        # When GUI is updated
        self.model.since = QDateTime.toPython(qdatetime)

    def on_since_model_changed(self, event):
        # When model is updated (e.g. from console or by clicking a QRadioButton)
        now = datetime.now(LOCAL_TIMEZONE)
        if isinstance(event.date, timedelta):
            qdatetime = as_qdatetime(now + event.date)
            if event.date == timedelta(minutes=-60):
                self.hour_widget.setChecked(True)
            elif event.date == timedelta(days=-1):
                self.today_widget.setChecked(True)
            elif event.date == timedelta(days=-7):
                self.week_widget.setChecked(True)
            elif event.date == timedelta(days=-30):
                self.month_widget.setChecked(True)
            elif event.date == timedelta(days=-365):
                self.year_widget.setChecked(True)
            else:
                # No checkbox associated with this custom timedelta
                pass
        else:
            # Must be a datetime
            if event.date == ADA_LOVELACE_BIRTHDAY:
                self.all_widget.setChecked(True)
            else:
                self.uncheck_radiobuttons()
            qdatetime = as_qdatetime(event.date)
        with _blocked(self.since_widget):
            self.since_widget.setDateTime(qdatetime)
        with _blocked(self.until_widget):
            self.until_widget.setDateTime(as_qdatetime(now))

    def on_until_view_changed(self, qdatetime):
        # When GUI is updated
        self.model.until = QDateTime.toPython(qdatetime)

    def on_until_model_changed(self, event):
        # When model is updated (e.g. from console or by clicking a QRadioButton)
        if not isinstance(event.date, timedelta):
            qdatetime = as_qdatetime(event.date)
            self.uncheck_radiobuttons()
            with _blocked(self.until_widget):
                self.until_widget.setDateTime(qdatetime)

    def on_toggle_24h(self):
        if self.today_widget.isChecked():
            self.model.since = timedelta(days=-1)
            self.model.until = timedelta()

    def on_toggle_hour(self):
        if self.hour_widget.isChecked():
            self.model.since = timedelta(minutes=-60)
            self.model.until = timedelta()

    def on_toggle_week(self):
        if self.week_widget.isChecked():
            self.model.since = timedelta(days=-7)
            self.model.until = timedelta()

    def on_toggle_month(self):
        if self.month_widget.isChecked():
            self.model.since = timedelta(days=-30)
            self.model.until = timedelta()

    def on_toggle_year(self):
        if self.year_widget.isChecked():
            self.model.since = timedelta(days=-365)
            self.model.until = timedelta()

    def on_toggle_all(self):
        # Search for all catalogs since Ada Lovelace's Birthday.
        if self.all_widget.isChecked():
            self.model.since = ADA_LOVELACE_BIRTHDAY
            self.model.until = timedelta()

    def uncheck_radiobuttons(self):
        self.radio_button_group.setExclusive(False)
        self.all_widget.setChecked(False)
        self.year_widget.setChecked(False)
        self.month_widget.setChecked(False)
        self.week_widget.setChecked(False)
        self.today_widget.setChecked(False)
        self.hour_widget.setChecked(False)
        self.radio_button_group.setExclusive(True)


@contextlib.contextmanager
def _blocked(qobject):
    "Block signals from this object inside the context."
    qobject.blockSignals(True)
    yield
    qobject.blockSignals(False)


# We need some concrete datetime to show in the "Since" datetime picker when
# the "All" button is checked. It should be some time old enough that it isn't
# likely to leave out wanted data. We cheekily choose this birthday as that
# time.
ADA_LOVELACE_BIRTHDAY = datetime(1815, 12, 10, tzinfo=LOCAL_TIMEZONE)
