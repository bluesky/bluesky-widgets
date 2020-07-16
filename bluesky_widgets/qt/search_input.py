from qtpy.QtCore import QDateTime
from qtpy.QtWidgets import (
    QDateTimeEdit,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QWidget,
    QPushButton,
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

        # "Since: <datetime picker>"
        self.since_widget = QDateTimeEdit()
        self.since_widget.setCalendarPopup(True)
        self.since_widget.setDisplayFormat("yyyy-MM-dd HH:mm")
        since_layout = QHBoxLayout()
        since_layout.addWidget(QLabel("Since:"))
        since_layout.addWidget(self.since_widget)
        since_layout_widget = QWidget()
        since_layout_widget.setLayout(since_layout)

        # "Until: <datetime picker>"
        self.until_widget = QDateTimeEdit()
        self.until_widget.setCalendarPopup(True)
        self.until_widget.setDisplayFormat("yyyy-MM-dd HH:mm")
        until_layout = QHBoxLayout()
        until_layout.addWidget(QLabel("Until:"))
        until_layout.addWidget(self.until_widget)
        until_layout_widget = QWidget()
        until_layout_widget.setLayout(until_layout)

        self.refresh_button = QPushButton("Refresh")

        # Stack them up.
        layout = QVBoxLayout()
        layout.addWidget(since_layout_widget)
        layout.addWidget(until_layout_widget)
        layout.addWidget(self.refresh_button)
        self.setLayout(layout)

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
        # Changes to the model update the GUI.
        self.model.events.since.connect(self.on_since_model_changed)
        self.model.events.until.connect(self.on_until_model_changed)

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
