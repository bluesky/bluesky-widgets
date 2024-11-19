import sys

from PyQt5.QtWidgets import QApplication

from bluesky_widgets.qt import tiled_auth

if __name__ == "__main__":
    app = QApplication(sys.argv)
    auth_manager = tiled_auth.TiledReaderManager()
    widget = tiled_auth.TiledAuthWidget(auth_manager=auth_manager)
    widget.show()
    # Can use the auth manager as a singleton in visualization widgets
    sys.exit(app.exec_())
