from qtpy.QtWidgets import QWidget, QVBoxLayout

from stream_widgets.qt.searches import QtSearches


class QtViewer(QWidget):
    """
    A Qt-based front-end to ViewerModel

    Take a ViewerModel and wrap each component in a correspdong QWidget, and
    arrange the widgets in a layout.

    This may be embedded in some other application's Main Window.
    """
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtSearches(model.searches))
