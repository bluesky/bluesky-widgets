"""
Use within IPython like

ipython --gui=qt

In [1]: %run -m bluesky_widgets.examples.ipy_qt_images
"""
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
from bluesky_widgets.models.plot_builders import Grid
from bluesky_widgets.qt.figures import QtFigure

catalog = get_catalog()
grid_scans = catalog.search({"plan_name": "grid_scan"})
run = grid_scans[-1]


model = Grid("det4", (3, 5))

model.run = run
view = QtFigure(model.figure)
view.show()
