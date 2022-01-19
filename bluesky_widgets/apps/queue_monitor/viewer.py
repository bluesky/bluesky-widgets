from bluesky_widgets.models.run_engine_client import RunEngineClient
from bluesky_widgets.qt import Window

from .widgets import QtViewer
from .settings import SETTINGS


class ViewerModel:
    """
    This encapsulates on the models in the application.
    """

    def __init__(self):
        self.run_engine = RunEngineClient(
            zmq_server_address=SETTINGS.zmq_re_manager_control_addr,
            zmq_subscribe_address=SETTINGS.zmq_re_manager_publish_addr,
        )


class Viewer(ViewerModel):
    """
    This extends the model by attaching a Qt Window as its view.

    This object is meant to be exposed to the user in an interactive console.
    """

    def __init__(self, *, show=True, title="Demo App"):
        # TODO Where does title thread through?
        super().__init__()
        widget = QtViewer(self)
        self._window = Window(widget, show=show)

    @property
    def window(self):
        return self._window

    def show(self):
        """Resize, show, and raise the window."""
        self._window.show()

    def close(self):
        """Close the window."""
        self._window.close()
