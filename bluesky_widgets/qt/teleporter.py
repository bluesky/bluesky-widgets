"""
The machinery makes it safe to call callbacks from a background thread.
It routes them through Qt Signals and Slots.

This is based on similar machinery originally developed in
bluesky.callbacks.mpl_plotting.
"""
import functools
import threading
from ..utils.event import Event

from qtpy import QtCore


MESSAGE = (
    "{module}.{name} may only be called from the main thread. It was called "
    "from the thread {thread}. To avoid this issue, first call "
    f"{__name__}.initialize_qt_teleporter from the main thread."
)


def initialize_qt_teleporter():
    """
    This must be called once from the main thread.

    Subsequent calls (from any thread) will have no effect.

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
            MESSAGE.format(module=__name__, name=initialize_qt_teleporter.__name__)
        )
    _get_teleporter()


@functools.lru_cache(maxsize=1)
def _get_teleporter():

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
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError(
            MESSAGE.format(module=__name__, name=threadsafe_connect.__name__)
        )
    teleporter = _get_teleporter()
    emitter.connect(lambda event: teleporter.obj_event.emit(callback, event))
