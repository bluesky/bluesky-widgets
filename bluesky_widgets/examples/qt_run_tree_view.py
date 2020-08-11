"""
Select some runs and click the button. Their IDs will be printed to the
terminal. In a real application, this could kick off data processing, export,
or visualization.
"""
from bluesky_widgets.qt import Window
from bluesky_widgets.qt import gui_qt
from bluesky_widgets.qt.run_tree import QtTreeView
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog

from qtpy.QtWidgets import QPushButton, QVBoxLayout, QWidget


class Views(QWidget):
    """
    A user-facing model composed with a Qt widget and window.
    """

    def __init__(self, *, show=True, title=""):
        super().__init__()
        self.title = title

        # ...and one listing any and all catalogs discovered on the system.
        from databroker import catalog

        # You can set your own catalog/run here or use this synthetic data.
        self._run = get_catalog()[-1]

        widget = QtTreeView(self, self._run)
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
        views = Views(title="Example Application")


if __name__ == "__main__":
    main()
