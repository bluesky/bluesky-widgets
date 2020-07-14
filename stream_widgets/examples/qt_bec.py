from stream_widgets.qt import Window
from stream_widgets.qt import gui_qt
from stream_widgets.examples.viewer_model import ViewerModel
from stream_widgets.examples.qt_viewer import QtViewer
from stream_widgets.examples.utils.generate_msgpack_data import get_catalog


class Viewer(ViewerModel):
    """
    The user-facing Qt-based Viewer.

    Compose the model with QtViewer and a Qt Main Window, so the user has just
    one object to handle.

    This cannot be embedded in another application's Main Window. Use QtViewer
    to do that.
    """
    def __init__(self, *, show=True, title=""):
        super().__init__(title=title)
        qt_viewer = QtViewer(self)
        self.window = Window(qt_viewer, show=show)

        # Initialize with a two search tabs: one with some generated example
        # data and one list any and all catalogs discovered on the system.
        self.add_search(get_catalog())
        from databroker import catalog
        self.add_search(catalog)

    def show(self):
        """Resize, show, and raise the viewer window."""
        self.window.show()

    def close(self):
        """Close the viewer window."""
        self.window.close()


def main():
    with gui_qt("Example Aplication"):
        viewer = Viewer()
        print(viewer)


if __name__ == "__main__":
    main()
