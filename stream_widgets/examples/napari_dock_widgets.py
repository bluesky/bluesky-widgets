import napari

from stream_widgets.components.search.search_input import SearchInput
from stream_widgets.qt.search_input import QtSearchInput

with napari.gui_qt():
    viewer = napari.Viewer()
    viewer.grid_view()  # Place images side by side, not stacked.
    viewer.window.add_dock_widget(QtSearchInput(SearchInput()), area="right")
