"""
Search for runs and visualize their data.

This example can be run alone as

$ python -m bluesky_widgets.examples.qt_viewer_with_search

or with the data streaming utility which will print an address to connect to

$ python -m bluesky_widgets.examples.utils.stream_data
Connect a consumer to localhost:XXXXX

python -m bluesky_widgets.examples.qt_viewer_with_search localhost:XXXXX
"""
from bluesky_widgets.models.viewer import Viewer
from bluesky_widgets.models.plot_builders import LastNLines
from bluesky_widgets.jupyter.viewer import JupyterViewer


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
        self.viewer = Viewer()
        self.viewer.streaming_builders.append(LastNLines("motor", "det", 3))
        self._widget = JupyterViewer(self.viewer)

    def _ipython_display_(self, *args, **kwargs):
        "When this object is displayed by Jupyter, display its widget."
        return self._widget._ipython_display_(*args, **kwargs)
