"""
Use within IPython like

ipython --gui=qt

In [1]: %run -m bluesky_widgets.examples.qt_figures
"""
from bluesky import RunEngine
from bluesky.plans import scan
from ophyd.sim import motor, det

from bluesky_widgets.utils.streaming import connect_dispatcher_to_list_of_runs
from bluesky_widgets.models.plot_builders import LastNLines
from bluesky_widgets.qt.figures import QtFigures
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog

model = LastNLines("motor", "det", 3)
view = QtFigures(model.figures)
view.show()

RE = RunEngine()
connect_dispatcher_to_list_of_runs(RE.dispatcher, model.runs)


catalog = get_catalog()
scans = catalog.search({"plan_name": "scan"})
model.pinned_runs.append(scans[-1])


def plan():
    for i in range(1, 5):
        yield from scan([det], motor, -1, 1, 1 + 2 * i)


RE(plan())
