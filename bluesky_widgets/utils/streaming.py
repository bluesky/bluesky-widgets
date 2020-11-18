from bluesky_live.bluesky_run import BlueskyRun, DocumentCache
import event_model


def connect_dispatcher_to_list_of_runs(dispatcher, runs):
    """
    Consume documents from a dispatcher and append BlueskyRuns to a list or runs.

    Parameters
    ----------
    dispatcher : Dispatcher
        Should implement subscribe() and push (name, doc) pairs.
    runs: EventedList
        List that will be appended to.
    """

    def factory(name, doc):
        dc = DocumentCache()

        def add_run_to_list(event):
            run = BlueskyRun(dc)
            runs.append(run)

        dc.events.started.connect(add_run_to_list)
        return [dc], []

    rr = event_model.RunRouter([factory])
    dispatcher.subscribe(rr)
