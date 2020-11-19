import functools
import threading
from ..utils.event import Event

from qtpy import QtCore


def initialize_qt_teleporter():
    """
    Set up the bluesky Qt 'teleporter'.

    This makes it safe to instantiate QtAwareCallback from a background thread.

    Raises
    ------
    RuntimeError
        If called from any thread but the main thread

    """
    if _get_teleporter.cache_info().currsize:
        # Already initialized.
        return
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError(
            "initialize_qt_teleporter() may only be called from the main " "thread."
        )
    _get_teleporter()


@functools.lru_cache(maxsize=1)
def _get_teleporter():

    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError(
            "threadsafe_connect was called from a background thread."
            "To avoid this issue, first call initialize_qt_teleporter "
            "from the main thread."
        )

    def handle_teleport(obj, event):
        obj(event)

    class Teleporter(QtCore.QObject):
        obj_event = QtCore.Signal(object, Event)

    t = Teleporter()
    t.obj_event.connect(handle_teleport)
    return t


def threadsafe_connect(emitter, callback):
    """
    Connect an EventEmitter to a callback via Qt Signal/Slot.

    This makes it safe for the EventEmitter to emit from a background thread.
    """
    teleporter = _get_teleporter()
    emitter.connect(lambda event: teleporter.obj_event.emit(callback, event))
