import napari

from bluesky_widgets.examples.utils.add_search_mixin import extract_results_row_from_run
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
from bluesky_widgets.examples.utils.get_run_images import generate_thumbnail
from bluesky_widgets.models.search import Search, SearchList
from bluesky_widgets.utils.event import Event
from qtpy.QtWidgets import QWidget, QPushButton, QVBoxLayout
from bluesky_widgets.qt.search import QtSearches


class SearchListWithButton(SearchList):
    """
    A SearchList model with a method to handle a click event.

    If we were to add a method of this class called on_view_images,
    then it would automatically receive view_images events without
    needing to use view_images.connect.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Register an event emitter for process events.
        # The kwarg view_images defines the name of the events that are emitted.
        # Event is the event type.
        self.events.add(view_images=Event)


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

        # Add a button that does something with the currently-selected Runs
        # when you click it.
        go_button = QPushButton("Process Selected Runs")
        layout.addWidget(go_button)

        # Register a callback (slot) for the button qt click signal.
        go_button.clicked.connect(self.on_click)

    def on_click(self):
        """
        Receive the qt signal, and emmit a view_images event.

        Add whatever we want to the event by passing it as a kwarg, in this case the images kwarg.
        Can access images in the callback by accessing Event.images.
        """
        thumbnails = [generate_thumbnail(run) for _, run in self.model.active.selection_as_catalog.items()]
        self.model.events.view_images(images=thumbnails)


class NapariDatabroker(napari.Viewer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.searches = SearchListWithButton()

        # Register the process event callback.
        self.searches.events.view_images.connect(self.load_images_from_run)

    def add_search(self, catalog, columns=extract_results_row_from_run):
        """
        Add a new Search form.
        """
        headings = (
            "Unique ID",
            "Transient Scan ID",
            "Plan Name",
            "Start Time",
            "Duration",
            "Exit Status",
        )

        search = Search(catalog, columns=(headings, extract_results_row_from_run))
        self.searches.append(search)

    @property
    def active_search(self):
        """
        Convenience for accessing the currently-active Search form.
        """
        return self.searches.active

    def load_images_from_run(self, view_images):
        """
        Handle a view_images event.
        """
        for thumbnail in view_images.images:
            self.add_image(thumbnail)


with napari.gui_qt():
    viewer = NapariDatabroker()
    viewer.grid.enabled = True
    viewer.window.add_dock_widget(QtSearchListWithButton(viewer.searches), area="right")

    # Initialize with a two search tabs: one with some generated example data...
    viewer.add_search(get_catalog())
    # ...and one listing any and all catalogs discovered on the system.
    from databroker import catalog

    viewer.add_search(catalog)
