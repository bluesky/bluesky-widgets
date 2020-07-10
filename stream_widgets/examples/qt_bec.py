from qtpy.QtWidgets import QWidget, QVBoxLayout

from stream_widgets.qt import Window
from stream_widgets.components.search.search_input import SearchInput
from stream_widgets.qt.search_input import QtSearchInput


class QtViewer(QWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewer = model
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtSearchInput(model.search_input))


class ViewerModel:
    def __init__(self, title):
        self.title = title
        self.search_input = SearchInput()
        super().__init__()


class Viewer(ViewerModel):

    def __init__(self, *, show=True, title=""):
        super().__init__(title=title)
        qt_viewer = QtViewer(self)
        self.window = Window(qt_viewer, show=show)

    def show(self):
        """Resize, show, and raise the viewer window."""
        self.window.show()

    def close(self):
        """Close the viewer window."""
        self.window.close()


def main():
    from stream_widgets.qt import gui_qt

    with gui_qt("Example Aplication"):
        Viewer()


if __name__ == "__main__":
    main()
