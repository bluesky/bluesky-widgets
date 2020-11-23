"""
Use within IPython like

ipython --gui=qt

In [1]: %run -m bluesky_widgets.examples.qt_figures
"""
from bluesky import RunEngine
from bluesky.plans import scan
from ophyd.sim import motor, det

from bluesky_widgets.utils.streaming import stream_documents_into_runs
from bluesky_widgets.models.plot_builders import AutoLastNLines
from bluesky_widgets.qt.figures import QtFigures
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog

model = AutoLastNLines(3)
view = QtFigures(model.figures)
view.show()

RE = RunEngine()
RE.subscribe(stream_documents_into_runs(model.runs.add_run))


catalog = get_catalog()
scans = catalog.search({"plan_name": "scan"})
model.pinned_runs.append(scans[-1])


def plan():
    for i in range(1, 5):
        yield from scan([det], motor, -1, 1, 1 + 2 * i)


RE(plan())
