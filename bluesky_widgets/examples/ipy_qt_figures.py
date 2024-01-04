"""
Use within IPython like

ipython --gui=qt

In [1]: %run -m bluesky_widgets.examples.ipy_qt_figures
"""
import pandas as pd

from bluesky import RunEngine
from bluesky.plans import scan
from ophyd.sim import motor, det

from bluesky_widgets.utils.streaming import stream_documents_into_runs
from bluesky_widgets.models.utils import call_or_eval
from bluesky_widgets.models.auto_plot_builders import AutoLines
from bluesky_widgets.qt.figures import QtFigures
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog

from bluesky.callbacks.core import LiveTable

import matplotlib.pyplot as plt

plt.plot(range(5))
plt.close("all")

model = AutoLines(max_runs=3)
view = QtFigures(model.figures)
view.show()

RE = RunEngine()
RE.subscribe(stream_documents_into_runs(model.add_run))


catalog = get_catalog()
scans = catalog.search({"plan_name": "scan"})
model.add_run(scans[-1], pinned=True)


def plan():
    for i in range(1, 5):
        yield from scan([det], motor, -1, 1, 1 + 2 * i)


catch = []


def test(run):
    catch.append(run)

    def handle_stream(evt):
        catch.append(evt)
        if evt.name != "primary":
            return
        count = 0
        run = evt.run
        cols = {f"col{j}": k for j, k in enumerate(run.primary.read())}

        def handle_data(evt):
            nonlocal count

            catch.append(evt)
            d = call_or_eval(cols, run, ["primary"])
            df = pd.DataFrame({k: v[count:] for k, v in d.items()})
            # print(df)
            count += len(df)

        run.events.new_data.connect(handle_data)
        lt = LiveTable(list(cols.values()))
        lt("start", run.metadata["start"])
        run.events.new_doc.connect(lambda event: lt(event.name, event.doc))

    run.events.new_stream.connect(handle_stream)


RE(plan(), stream_documents_into_runs(test))
