"""
Select some runs and click the button. Their IDs will be printed to the
terminal. In a real application, this could kick off data processing, export,
or visualization.
"""
from bluesky_widgets.qt import Window
from bluesky_widgets.qt import gui_qt
from bluesky_widgets.models.search import SearchList, Search
from bluesky_widgets.models.viewer import Viewer, consumer
from bluesky_widgets.qt.search import QtSearches
from bluesky_widgets.qt.viewer import QtViewer
from bluesky_widgets.utils.event import Event
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
from bluesky_widgets.examples.utils.add_search_mixin import columns
from qtpy.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout


class SearchListWithButton(SearchList):
    """
    A SearchList model with a method to handle a click event.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events.add(view=Event)


class QtSearchListWithButton(QWidget):
    """
    A view for SearchListWithButton.

    Combines the QtSearches widget with a button that processes the selected Runs.
    """

    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtSearches(model))

        go_button = QPushButton("View Selected Runs")
        layout.addWidget(go_button)
        go_button.clicked.connect(self.model.events.view)


class SearchAndView:
    def __init__(self, searches, viewer):
        self.searches = searches
        self.viewer = viewer
        self.searches.events.view.connect(self._on_view)

    def _on_view(self, event):
        for uid, run in self.searches.active.selection_as_catalog.items():
            self.viewer.runs.append(run)


class QtSearchAndView(QWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        layout = QHBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtSearchListWithButton(model.searches))
        layout.addWidget(QtViewer(model.viewer))


class ExampleApp:
    """
    A user-facing model composed with a Qt widget and window.

    A key point here is that the model `searches` is public and can be
    manipuated from a console, but the view `_window` and all Qt-related
    components are private. The public `show()` and `close()` methods are the
    only view-specific actions that are exposed to the user. Thus, this could
    be implemented in another UI framework with no change to the user-facing
    programmatic interface.
    """

    def __init__(self, *, show=True, title="Example App"):
        super().__init__()
        self.title = title
        self.searches = SearchListWithButton()
        self.viewer = Viewer()
        self.model = SearchAndView(self.searches, self.viewer)
        self.model.viewer.consumers.append(consumer)
        widget = QtSearchAndView(self.model)
        self._window = Window(widget, show=show)

        # Initialize with a two search tabs: one with some generated example data...
        self.searches.append(Search(get_catalog(), columns=columns))
        # ...and one listing any and all catalogs discovered on the system.
        from databroker import catalog

        self.model.searches.append(Search(catalog, columns=columns))

    def show(self):
        """Resize, show, and raise the window."""
        self._window.show()

    def close(self):
        """Close the window."""
        self._window.close()


def main():
    print(__doc__)
    with gui_qt("Example App"):
        app = ExampleApp()

        # We can access and modify the model as in...
        len(app.searches)
        app.searches[0]
        app.searches.active  # i.e. current tab
        app.searches.active.input.since  # time range
        app.searches.active.input.until
        app.searches.active.results
        app.searches.active.selection_as_catalog
        app.searches.active.selected_uids


if __name__ == "__main__":
    main()
