from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
from bluesky_widgets.models.plot_builders import PromptPlotter
from bluesky_widgets.models.plot_specs import AxesSpec, ImageSpec, FigureSpec
from bluesky_widgets.qt.figures import QtFigures

catalog = get_catalog()
counts = catalog.search({"plan_name": "count"})
run = counts[-1]


def prompt_image_builder(run):
    """
    This is a simple example.
    This makes a hard-coded assumption that the data has columns "motor" and
    "det" in the primary stream.
    """

    def func(run):
        "Return any arrays x, y. They must be of equal length."
        # *Lazily* read the data so that large arrays are not loaded unless
        # they are used.
        ds = run.primary.read()
        # Do any computation you want in here....
        return ds["random_img"].data.sum((0, 1))

    image_spec = ImageSpec(func, run, label="random_img")
    axes_spec = AxesSpec(images=[image_spec])
    figure_spec = FigureSpec((axes_spec,), title="random_img")

    return figure_spec


model = PromptPlotter([prompt_image_builder])

model.runs.append(run)
view = QtFigures(model.figures)
view.show()
