from bluesky_widgets.models.run_engine_client import RunEngineClient
from bluesky_widgets.qt import Window

from .widgets import QtViewer
from .settings import SETTINGS

from qtpy.QtWidgets import QAction


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

        self._widget = QtViewer(self)
        self._window = Window(self._widget, show=show)

        menu_bar = self._window._qt_window.menuBar()
        menu_item_control = menu_bar.addMenu("Control Actions")
        self.action_activate_env_destroy = QAction("Activate 'Destroy Environment'", self._window._qt_window)
        self.action_activate_env_destroy.setCheckable(True)
        self._update_action_env_destroy_state()
        self.action_activate_env_destroy.triggered.connect(self._activate_env_destroy_triggered)
        menu_item_control.addAction(self.action_activate_env_destroy)

        self._widget.model.run_engine.events.status_changed.connect(self.on_update_widgets)

    def _update_action_env_destroy_state(self):
        env_destroy_activated = self._widget.model.run_engine.env_destroy_activated
        self.action_activate_env_destroy.setChecked(env_destroy_activated)

    def _activate_env_destroy_triggered(self):
        env_destroy_activated = self._widget.model.run_engine.env_destroy_activated
        self._widget.model.run_engine.activate_env_destroy(not env_destroy_activated)

    def on_update_widgets(self, event):
        self._update_action_env_destroy_state()

    @property
    def window(self):
        return self._window

    def show(self):
        """Resize, show, and raise the window."""
        self._window.show()

    def close(self):
        """Close the window."""
        self._window.close()
