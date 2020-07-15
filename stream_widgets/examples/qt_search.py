"""
Select some runs and click the button. Their IDs will be printed to the
terminal. In a real application, this could kick off data processing, export,
or visualization.
"""
from stream_widgets.qt import Window
from stream_widgets.qt import gui_qt
from stream_widgets.components.search.searches import SearchList, Search
from stream_widgets.qt.searches import QtSearches
from stream_widgets.examples.utils.generate_msgpack_data import get_catalog
from stream_widgets.examples.utils.add_search_mixin import columns

from qtpy.QtWidgets import QPushButton, QVBoxLayout, QWidget


class SearchesWidget(QWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtSearches(model))

        # Add a button that does something with the currently-selected Runs
        # when you click it.
        go_button = QPushButton("Process Selected Runs")
        # We'll just slip this into an existing widget --- not great form, but
        # this is just a silly example.
        layout.addWidget(go_button)
        go_button.clicked.connect(self.on_click)

    def on_click(self):
        for uid, run in self.model.active.selection_as_catalog.items():
            # Pretend to kick off data processing or something.
            print(f"Processing Run {uid[:8]} (scan_id={run.metadata['start']['scan_id']})")


class Searches(SearchList):
    """
    A user-facing Qt-based Search Window.
    """
    def __init__(self, *, show=True, title=""):
        super().__init__()
        self.title = title
        widget = SearchesWidget(self)
        self.window = Window(widget, show=show)

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

        # Initialize with a two search tabs: one with some generated example data...
        searches.append(Search(get_catalog(), columns=columns))
        # ...and one listing any and all catalogs discovered on the system.
        from databroker import catalog
        searches.append(Search(catalog, columns=columns))


if __name__ == "__main__":
    main()
