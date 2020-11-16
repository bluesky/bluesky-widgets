"""
Displays a BlueskyRun in a QTreeView lazily populating the view. In a real
application this would be used in conjunction with a data browser/search box or
on the command line to explore runs.
"""
from bluesky_widgets.qt import Window
from bluesky_widgets.qt import gui_qt
from bluesky_widgets.qt.run_tree import QtTreeView
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog

from qtpy.QtWidgets import QWidget


class Views(QWidget):
    """
    A user-facing model composed with a Qt widget and window.
    """

    def __init__(self, *, show=True, title=""):
        super().__init__()
        self.title = title
        self.widget = QtTreeView(self)

    def set_run(self, bs_run):
        self.widget.model().setRun(bs_run)

class RunTree:
    """
    A user-facing model composed with a Qt widget and window.
    """

    def __init__(self, *, show=True, title="Bluesky run tree"):
        super().__init__()
        self.title = title
        self.view = Views()
        self._window = Window(self.view.widget, show=show)

    def set_run(self, bs_run):
        """Set the active run to the one supplied."""
        self.view.set_run(bs_run)

    def show(self):
        """Resize, show, and raise the window."""
        self.window.show()

    def close(self):
        """Close the window."""
        self.window.close()

def main():
    print(__doc__)
    with gui_qt("Example Application"):
        views = Views(title="Example Application")

        # You can set your own catalog/run here or use this synthetic data.
        run = get_catalog()[-1]
        views.set_run(run)

        views.show()


if __name__ == "__main__":
    main()
