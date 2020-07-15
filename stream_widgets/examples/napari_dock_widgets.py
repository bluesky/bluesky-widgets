import napari

from stream_widgets.components.search.searches import SearchList
from stream_widgets.qt.searches import QtSearches
from stream_widgets.examples.viewer_model import AddSearchMixin
from stream_widgets.examples.utils.generate_msgpack_data import get_catalog


class Viewer(napari.Viewer, AddSearchMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.searches = SearchList()


with napari.gui_qt():
    viewer = Viewer()
    viewer.grid_view()  # Place images side by side, not stacked.
    viewer.window.add_dock_widget(QtSearches(viewer.searches), area="right")
    viewer.add_search(get_catalog())
