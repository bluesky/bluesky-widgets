"""
Search for runs and visualize their data.

This example can be run alone as

$ python -m bluesky_widgets.examples.qt_viewer_with_search

or with the data streaming utility which will print an address to connect to

$ python -m bluesky_widgets.examples.utils.stream_data_zmq
Connect a consumer to localhost:XXXXX

python -m bluesky_widgets.examples.qt_viewer_with_search localhost:XXXXX
"""
from bluesky_widgets.models.auto_plot_builders import AutoLines
from bluesky_widgets.jupyter.figures import JupyterFigures


class ExampleApp:
    """
    A user-facing model composed with a Qt widget and window.

    A key point here is that the model `searches` is public and can be
    manipuated from a console, but the view `_window` and all Qt-related
    components are private. The public `show()` and `close()` methods are the
    only view-specific actions that are exposed to the user. Thus, this could
    be implemented in another UI framework with no change to the user-facing
    programmatic interface.
    """

    def __init__(self, *, show=True, title="Example App"):
        super().__init__()
        self.title = title
        self.model = AutoLines(max_runs=3)
        self._widget = JupyterFigures(self.model.figures)

    def _ipython_display_(self, *args, **kwargs):
        "When this object is displayed by Jupyter, display its widget."
        return self._widget._ipython_display_(*args, **kwargs)


def listen_for_data(app, address):
    # Optional: Receive live streaming data.
    from bluesky_widgets.jupyter.zmq_dispatcher import RemoteDispatcher
    from bluesky_widgets.utils.streaming import stream_documents_into_runs

    dispatcher = RemoteDispatcher(address)
    dispatcher.subscribe(stream_documents_into_runs(app.model.add_run))
    dispatcher.start()  # launches process and thread
    return dispatcher.stop
