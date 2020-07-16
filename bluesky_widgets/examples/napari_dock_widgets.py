import napari

from bluesky_widgets.components.search.searches import SearchList
from bluesky_widgets.qt.searches import QtSearches
from bluesky_widgets.examples.utils.add_search_mixin import AddSearchMixin
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog


class Viewer(napari.Viewer, AddSearchMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.searches = SearchList()


with napari.gui_qt():
    viewer = Viewer()
    viewer.grid_view()  # Place images side by side, not stacked.
    viewer.window.add_dock_widget(QtSearches(viewer.searches), area="right")

    # Initialize with a two search tabs: one with some generated example data...
    viewer.add_search(get_catalog())
    # ...and one listing any and all catalogs discovered on the system.
    from databroker import catalog

    viewer.add_search(catalog)
