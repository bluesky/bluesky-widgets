"""
An example integration QtFigures into an "existing" Qt application. Run like:

python -m bluesky_widgets.examples.qt_app_integration
"""
from qtpy.QtWidgets import (
    QApplication,
    QPushButton,
    QVBoxLayout,
    QLabel,
    QMainWindow,
    QWidget,
)
from bluesky_widgets.models.search import Search
from bluesky_widgets.qt.search import QtSearch
from bluesky_live.event import Event


# Extend the search widget with a single button. In your application, you might
# want multiple buttons that do different things.


class SearchAndOpen(Search):
    """
    Extend Search model with a signal for when a result is "opened".

    In your application, you might have multiple such signals associated with
    different buttons.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events.add(open=Event)

    @property
    def selected_runs(self):
        # This property would be useful in general and should be added to the
        # Search itself in bluesky-widgets.
        return [self.results[uid] for uid in self.selected_uids]


class QtSearchListWithButton(QWidget):
    """
    A view for SearchAndOpen.

    Combines the QtSearches widget with a button.
    """

    def __init__(self, model: SearchAndOpen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtSearch(model))

        # Add a button that does something with the currently-selected Runs
        # when you click it.
        self._open_button = QPushButton("Open")
        layout.addWidget(self._open_button)

        # Register a callback (slot) for the button qt click signal.
        self._open_button.clicked.connect(self._on_click_open_button)

    def _on_click_open_button(self):
        """
        Receive the Qt signal and emit a bluesky-widgets one.

        Include a list of BlueskyRuns corresponding to the current selection.
        """
        self.model.events.open(selected_runs=self.model.selected_runs)


# Customize what is shown in the search results here.

headings = (
    "Unique ID",
    "Transient Scan ID",
    "Plan Name",
    "Scanning",
    "Start Time",
    "Duration",
    "Exit Status",
)


def extract_results_row_from_run(run):
    """
    Given a BlueskyRun, format a row for the table of search results.
    """
    from datetime import datetime

    metadata = run.describe()["metadata"]
    start = metadata["start"]
    stop = metadata["stop"]
    start_time = datetime.fromtimestamp(start["time"])
    if stop is None:
        str_duration = "-"
    else:
        duration = datetime.fromtimestamp(stop["time"]) - start_time
        str_duration = str(duration)
        str_duration = str_duration[: str_duration.index(".")]
    return (
        start["uid"][:8],
        start.get("scan_id", "-"),
        start.get("plan_name", "-"),
        str(start.get("motors", "-")),
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
        str_duration,
        "-" if stop is None else stop["exit_status"],
    )


columns = (headings, extract_results_row_from_run)


def main():
    # First, some boilerplate to make a super-minimal Qt application that we want
    # to add some bluesky-widgets components into.
    app = QApplication(["Some App"])
    window = QMainWindow()
    central_widget = QWidget(window)
    window.setCentralWidget(central_widget)
    central_widget.setLayout(QVBoxLayout())
    central_widget.layout().addWidget(QLabel("This is part of the 'original' app."))
    window.show()

    # *** INTEGRATION WITH BLUESKY-WIDGETS STARTS HERE. ***

    # Ensure that any background workers started by bluesky-widgets stop
    # gracefully when the application closes.
    from bluesky_widgets.qt.threading import wait_for_workers_to_quit

    app.aboutToQuit.connect(wait_for_workers_to_quit)

    # Get the catalog (must be databroker.v2-style).
    CATALOG_NAME = "example"
    import databroker

    catalog = databroker.catalog[CATALOG_NAME]
    # Create an instance of our model.
    search_model = SearchAndOpen(catalog, columns=columns)
    # Define what to do when the signal associated with the "Open" button fires.
    # In this toy example, just print to the terminal.
    search_model.events.open.connect(lambda event: print(f"Opening {event.selected_runs}"))
    # Create a Qt "view" of this model...
    search_view = QtSearchListWithButton(search_model)
    # ...and place it in our app.
    central_widget.layout().addWidget(search_view)

    # *** INTEGRATION WITH BLUESKY-WIDGETS ENDS HERE. ***

    # Run the app.
    app.exec_()


if __name__ == "__main__":
    main()
