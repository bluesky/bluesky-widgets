"""
Use within IPython like

ipython --gui=qt

In [1]: %run -m bluesky_widgets.examples.ipy_qt_images
"""
from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
from bluesky_widgets.models.plot_builders import Image
from bluesky_widgets.qt.figures import QtFigure

catalog = get_catalog()
counts = catalog.search({"plan_name": "count"})
run = counts[-1]


model = Image("random_img")

model.run = run
view = QtFigure(model.figure)
view.show()
