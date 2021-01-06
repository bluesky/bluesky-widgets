from bluesky_live.bluesky_run import BlueskyRun, DocumentCache
import event_model


def stream_documents_into_runs(add_run):
    """
    Convert a flat stream of documents to "live" BlueskyRuns.

    Parameters
    ----------
    add_run : callable
        This will be called as ``add_run(run: BlueskyRun)`` each time a 'start'
        document is received.

    Returns
    -------
    callback : callable
        This should be subscribed to a callback registry that calls it like
        ``callback(name, doc)``.

    Examples
    --------

    This is used for connecting something that emits a flat stream of documents
    to something that wants to receive BlueskyRuns.

    Append to a plain list.

    >>> from bluesky import RunEngine
    >>> RE = RunEngine()
    >>> runs = []
    >>> RE.subscribe(stream_documents_into_runs(runs.append))

    Or, more usefully to an observable list.

    >>> from bluesky_widgets.models.utils import RunList
    >>> runs = RunList()
    >>> RE.subscribe(stream_documents_into_runs(runs.append))

    Add runs to a model with an ``add_run`` method. For example, it might be a
    model that generates figures.

    >>> from bluesky_widgets.models.plot_builders import AutoLines
    >>> model = AutoLines()

    >>> RE.subscribe(stream_documents_into_runs(model.add_run))
    """

    def factory(name, doc):
        dc = DocumentCache()

        def build_and_add_run(event):
            run = BlueskyRun(dc)
            add_run(run)

        dc.events.started.connect(build_and_add_run)
        return [dc], []

    rr = event_model.RunRouter([factory])
    return rr
