import os

from qtpy.QtWidgets import QAction, QFileDialog

from bluesky_widgets.models.run_engine_client import RunEngineClient
from bluesky_widgets.qt import Window

from .settings import SETTINGS
from .widgets import QtViewer


class ViewerModel:
    """
    This encapsulates on the models in the application.
    """

    def __init__(self):
        self.run_engine = RunEngineClient(
            zmq_control_addr=SETTINGS.zmq_re_manager_control_addr,
            zmq_info_addr=SETTINGS.zmq_re_manager_info_addr,
            http_server_uri=SETTINGS.http_server_uri,
            http_server_api_key=SETTINGS.http_server_api_key,
        )


class Viewer(ViewerModel):
    """
    This extends the model by attaching a Qt Window as its view.

    This object is meant to be exposed to the user in an interactive console.
    """

    def __init__(self, *, show=True, title="Demo App"):
        # TODO Where does title thread through?
        super().__init__()

        self._work_dir = os.path.expanduser("~")

        self._widget = QtViewer(self)
        self._window = Window(self._widget, show=show)

        menu_bar = self._window._qt_window.menuBar()
        menu_item_control = menu_bar.addMenu("Control Actions")
        self.action_activate_env_destroy = QAction("Activate 'Destroy Environment'", self._window._qt_window)
        self.action_activate_env_destroy.setCheckable(True)
        self._update_action_env_destroy_state()
        self.action_activate_env_destroy.triggered.connect(self._activate_env_destroy_triggered)
        menu_item_control.addAction(self.action_activate_env_destroy)

        menu_item_control = menu_bar.addMenu("Save/Restore")
        self.action_save_history_as_txt = QAction("Save Plan History (as .txt)", self._window._qt_window)
        self.action_save_history_as_txt.triggered.connect(self._save_history_as_txt_triggered)
        menu_item_control.addAction(self.action_save_history_as_txt)
        self.action_save_history_as_json = QAction("Save Plan History (as .json)", self._window._qt_window)
        self.action_save_history_as_json.triggered.connect(self._save_history_as_json_triggered)
        menu_item_control.addAction(self.action_save_history_as_json)
        self.action_save_history_as_yaml = QAction("Save Plan History (as .yaml)", self._window._qt_window)
        self.action_save_history_as_yaml.triggered.connect(self._save_history_as_yaml_triggered)
        menu_item_control.addAction(self.action_save_history_as_yaml)

        self._widget.model.run_engine.events.status_changed.connect(self.on_update_widgets)

    def _update_action_env_destroy_state(self):
        env_destroy_activated = self._widget.model.run_engine.env_destroy_activated
        self.action_activate_env_destroy.setChecked(env_destroy_activated)

    def _activate_env_destroy_triggered(self):
        env_destroy_activated = self._widget.model.run_engine.env_destroy_activated
        self._widget.model.run_engine.activate_env_destroy(not env_destroy_activated)

    def _save_history_as_txt_triggered(self):
        self._save_history_to_file("txt")

    def _save_history_as_json_triggered(self):
        self._save_history_to_file("json")

    def _save_history_as_yaml_triggered(self):
        self._save_history_to_file("yaml")

    def _save_history_to_file(self, file_format):
        try:
            fln_pattern = f"{file_format.upper()} (*.{file_format.lower()});; All (*)"
            file_path_init = os.path.join(self._work_dir, "plan_history." + file_format.lower())
            file_path_tuple = QFileDialog.getSaveFileName(
                self._widget, "Save Plan History to File", file_path_init, fln_pattern
            )
            file_path = file_path_tuple[0]
            if file_path:
                file_path = file_path_tuple[0]
                self._work_dir = os.path.dirname(file_path)
                self._widget.model.run_engine.save_plan_history_to_file(
                    file_path=file_path, file_format=file_format
                )
                print(f"Plan history was successfully saved to file {file_path!r}")
        except Exception as ex:
            print(f"Failed to save data to file: {ex}")

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
