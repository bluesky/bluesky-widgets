"""
Select some runs and click the button. Their IDs will be printed to the
terminal. In a real application, this could kick off data processing, export,
or visualization.
"""
from datetime import datetime

from bluesky_widgets.qt import Window
from bluesky_widgets.qt import gui_qt
from bluesky_widgets.components.search.searches import SearchList, Search
from bluesky_widgets.qt.searches import QtSearches
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
from bluesky_widgets.examples.utils.add_search_mixin import columns

from qtpy.QtWidgets import QPushButton, QVBoxLayout, QWidget


class SearchesWidget(QWidget):
    """
    Combine the QtSearches widget with a button that processes selected Runs.
    """

    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtSearches(model))

        # Add a button that does something with the currently-selected Runs
        # when you click it.
        go_button = QPushButton("Process Selected Runs")
        layout.addWidget(go_button)
        go_button.clicked.connect(self.on_click)

    def on_click(self):
        for uid, run in self.model.active.selection_as_catalog.items():
            # Pretend to kick off data processing or something.
            print(
                f"Processing Run {uid[:8]} (scan_id={run.metadata['start']['scan_id']})"
            )


class Searches(SearchList):
    """
    A user-facing model composed with a Qt widget and window.
    """

    def __init__(self, *, show=True, title=""):
        super().__init__()
        self.title = title
        widget = SearchesWidget(self)
        self.window = Window(widget, show=show)

        # Initialize with a two search tabs: one with some generated example data...
        self.append(Search(get_catalog(), columns=columns))
        # ...and one listing any and all catalogs discovered on the system.
        from databroker import catalog

        self.append(Search(catalog, columns=columns))

    def show(self):
        """Resize, show, and raise the window."""
        self.window.show()

    def close(self):
        """Close the window."""
        self.window.close()


def main():
    print(__doc__)
    with gui_qt("Example Application"):
        searches = Searches(title="Example Application")

        # We can access and modify the model as in...
        len(searches)
        searches[0]
        searches.active  # i.e. current tab
        searches.active.input.since  # time range
        searches.active.input.until = datetime(2040, 1, 1)
        searches.active.results
        searches.active.selection_as_catalog
        searches.active.selected_uids


if __name__ == "__main__":
    main()
