"""
Run like

python -m bluesky_widgets.examples.napari_image_gallery bluesky-tutorial-RSOXS Synced_waxs_image
"""
from distutils.version import LooseVersion
import warnings

import napari
from qtpy.QtWidgets import QWidget, QPushButton, QVBoxLayout

from bluesky_widgets.models.search import Search
from bluesky_widgets.utils.event import Event
from bluesky_widgets.qt.search import QtSearch
import bluesky_widgets.models.plot_builders
import bluesky_widgets.models.plot_specs


if LooseVersion(napari.__version__) < LooseVersion("0.4.4"):
    warnings.warn(
        f"This is tested on napari >= 0.4.4 but you have napari {napari.__version__}"
    )


class SearchAndOpen(Search):
    """
    A Search model with a new signal for when a result is "opened".
    """

    def __init__(self, *args, field, **kwargs):
        super().__init__(*args, **kwargs)
        self.events.add(open=Event)


class QtSearchListWithButton(QWidget):
    """
    A view for SearchAndOpen.

    Combines the QtSearches widget with a button.
    """

    def __init__(self, model: SearchAndOpen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtSearch(model))

        # Add a button that does something with the currently-selected Runs
        # when you click it.
        self._open_button = QPushButton("Open")
        layout.addWidget(self._open_button)

        # Register a callback (slot) for the button qt click signal.
        self._open_button.clicked.connect(self._on_click_open_button)

    def _on_click_open_button(self):
        """
        Receive the qt signal, and emmit a view_images event.

        Add whatever we want to the event by passing it as a kwarg, in this case the images kwarg.
        Can access images in the callback by accessing Event.images.
        """
        self.model.events.open()


class NapariFigureView:
    def __init__(self, model, napari_viewer):
        self.model = model
        # SHORTCUT: Assume one axes.
        self.model.axes[0].artists.events.added.connect(self._on_artist_added)
        # Place images side by side, not stacked.
        self.napari_viewer = napari_viewer
        self._layers = {}

    def _on_artist_added(self, event):
        artist_spec = event.item
        if isinstance(artist_spec, bluesky_widgets.models.plot_specs.Image):
            DECIMATION = 1

            def process_update(update):
                arr = update["array"]
                # Do something with update["array"]
                for i, plane in enumerate(arr[::DECIMATION]):
                    # coarse_plane = plane.coarsen({"dim_3": 5, "dim_4": 5, "dim_5": 5}, boundary="trim").mean()
                    name = f"{i}"
                    self.napari_viewer.layers.clear()
                    layer = self.napari_viewer.add_image(plane, name=name)
                    self._layers[artist_spec.uuid] = layer
                # self.napari_viewer.grid.enabled = True
                self.napari_viewer.grid_view()

            def handle_new_data(event):
                print('handling new data')
                process_update(artist_spec.update())

            artist_spec.events.new_data.connect(handle_new_data)
            artist_spec.events.completed.disconnect(handle_new_data)
        else:
            # Ignore anything that is not an image.
            # TODO Plot lines in a matplotlib figure in the side bar?
            pass


    def _on_artist_removed(self, event):
        artist_spec = event.item
        layer = self._layers.pop(artist_spec.uuid, None)
        if layer is not None:
            self.napari_viewer.layers.remove(layer)


# Customize what is shown in the search results here.

headings = (
    "Unique ID",
    "Transient Scan ID",
    "Plan Name",
    "Scanning",
    "Start Time",
    "Duration",
    "Exit Status",
)


def extract_results_row_from_run(run):
    """
    Given a BlueskyRun, format a row for the table of search results.
    """
    from datetime import datetime

    metadata = run.describe()["metadata"]
    start = metadata["start"]
    stop = metadata["stop"]
    start_time = datetime.fromtimestamp(start["time"])
    if stop is None:
        str_duration = "-"
    else:
        duration = datetime.fromtimestamp(stop["time"]) - start_time
        str_duration = str(duration)
        str_duration = str_duration[: str_duration.index(".")]
    return (
        start["uid"][:8],
        start.get("scan_id", "-"),
        start.get("plan_name", "-"),
        str(start.get("motors", "-")),
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
        str_duration,
        "-" if stop is None else stop["exit_status"],
    )


columns = (headings, extract_results_row_from_run)


class ImageGallery(bluesky_widgets.models.plot_builders.Images):
    """
    A model of an image gallery

    To be viewed in napari and eventually others (e.g. Jupyter)
    """

    # NOTE: This is sketchy, overriding a private method, subject to breaking
    # changes in future releases of bluesky-widgets.
    def _transform(self, run, field):
        from bluesky_widgets.models.utils import call_or_eval

        result = call_or_eval({"array": field}, run, self.needs_streams, self.namespace)
        # Manipulate result["array"] here if need be.
        return result


def main(catalog_name, field):
    import databroker

    catalog = databroker.catalog[catalog_name]
    with napari.gui_qt():
        viewer = napari.Viewer()

        # Define our models of the search and the gallery.
        search_model = SearchAndOpen(catalog, columns=columns, field=field)

        gallery_model = ImageGallery(
            lambda run: run.primary.to_dask()[field]
            - run.dark.to_dask()[field].mean("time"),
            max_runs=1,
        )
        search_model.events.open.connect(
            lambda event: gallery_model.add_run(search_model.active_run)
        )

        napari_figure_view = NapariFigureView(gallery_model.figure, viewer)  # noqa F841

        # Add our custom Search sidebar widget.
        search_view = QtSearchListWithButton(search_model)
        viewer.window.add_dock_widget(search_view, area="right")


if __name__ == "__main__":
    import sys

    main(sys.argv[1], sys.argv[2])
