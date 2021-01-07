"""
Use within IPython like

ipython --gui=qt

In [1]: %run -m bluesky_widgets.examples.ipy_qt_rastered_image
"""
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
from bluesky_widgets.models.plot_builders import RasteredImages
from bluesky_widgets.qt.figures import QtFigure

catalog = get_catalog()
grid_scans = catalog.search({"plan_name": "grid_scan"})
run = grid_scans[-1]

model = RasteredImages("det4", (5, 7))

model.add_run(run)
view = QtFigure(model.figure)
view.show()
