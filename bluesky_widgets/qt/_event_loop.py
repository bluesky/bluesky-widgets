from contextlib import contextmanager

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication

from .threading import wait_for_workers_to_quit


_our_app_name = None


def get_our_app_name():
    return _our_app_name


@contextmanager
def gui_qt(app_name):
    """Start a Qt event loop in which to run the application.

    Parameters
    ----------
    app_name: str

    Notes
    -----
    This context manager is not needed if running the app within an interactive
    IPython session. In this case, use the ``%gui qt`` magic command, or start
    IPython with the Qt GUI event loop enabled by default by using
    ``ipython --gui=qt``.
    """
    app = QApplication.instance()
    if not app:
        # automatically determine monitor DPI.
        # Note: this MUST be set before the QApplication is instantiated
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        # if this is the first time the Qt app is being instantiated, we set
        # the name, so that we know whether to raise_ in Window.show()
        app = QApplication([app_name])
        global _our_app_name
        _our_app_name = app_name
    else:
        app._existed = True
    app.aboutToQuit.connect(wait_for_workers_to_quit)
    yield app
    # if the application already existed before this function was called,
    # there's no need to start it again.  By avoiding unnecessary calls to
    # ``app.exec_``, we avoid blocking.
    if app.applicationName() == app_name:
        app.exec_()
