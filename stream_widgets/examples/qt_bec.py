from qtpy.QtWidgets import QWidget

from stream_widgets.qt import Window


class QtViewer(QWidget):
    def __init__(self, model, *args, **kwargs):
        self.viewer = model
        super().__init__(*args, **kwargs)


class ViewerModel:
    def __init__(self, title):
        self.title = title
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
