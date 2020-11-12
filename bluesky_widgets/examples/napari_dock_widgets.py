import napari

from bluesky_widgets.examples.qt_search import SearchListWithButton, QtSearchListWithButton
from bluesky_widgets.examples.utils.add_search_mixin import extract_results_row_from_run
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
from bluesky_widgets.models.search import Search

headings = (
    "Unique ID",
    "Transient Scan ID",
    "Plan Name",
    "Start Time",
    "Duration",
    "Exit Status",
)

class NapariDatabroker(napari.Viewer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.searches = SearchListWithButton()

    def add_search(self, catalog, columns=extract_results_row_from_run):
        """
        Add a new Search form.
        """
        search = Search(catalog, columns=(headings, extract_results_row_from_run))
        self.searches.append(search)

    @property
    def active_search(self):
        """
        Convenience for accessing the currently-active Search form.
        """
        return self.searches.active


with napari.gui_qt():
    viewer = NapariDatabroker()
    viewer.grid_view()  # Place images side by side, not stacked.
    viewer.window.add_dock_widget(QtSearchListWithButton(viewer.searches), area="right")

    # Initialize with a two search tabs: one with some generated example data...
    viewer.add_search(get_catalog())
    # ...and one listing any and all catalogs discovered on the system.
    from databroker import catalog

    viewer.add_search(catalog)
