"""
Displays a BlueskyRun in a QTreeView lazily populating the view. In a real
application this would be used in conjunction with a data browser/search box or
on the command line to explore runs.
"""
from bluesky_widgets.models.run_tree import RunTree
from bluesky_widgets.qt import Window
from bluesky_widgets.qt import gui_qt
from bluesky_widgets.qt.run_tree import QtTreeView
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog


class RunTree(RunTree):
    """
    A user-facing model extended with a Qt widget and window.
    """

    def __init__(self, run=None, *, show=True, title="Bluesky run tree"):
        super().__init__(run=run)
        self.title = title
        widget = QtTreeView(self)
        self._window = Window(widget, show=show)

    def show(self):
        """Resize, show, and raise the window."""
        self._window.show()

    def close(self):
        """Close the window."""
        self._window.close()


def main():
    print(__doc__)
    with gui_qt("Example Application"):
        tree = RunTree(title="Example Application")

        # You can set your own catalog/run here or use this synthetic data.
        run = get_catalog()[-1]
        tree.run = run


if __name__ == "__main__":
    main()
