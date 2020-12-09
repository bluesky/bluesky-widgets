"""
Use within IPython like

ipython --gui=qt

In [1]: %run -m bluesky_widgets.examples.ipy_qt_images
"""
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
from bluesky_widgets.models.auto_plot_builders import AutoImages
from bluesky_widgets.qt.figures import QtFigures

catalog = get_catalog()
counts = catalog.search({"plan_name": "count"})
run = counts[-1]


model = AutoImages()

model.add_run(run)
view = QtFigures(model.figures)
view.show()
