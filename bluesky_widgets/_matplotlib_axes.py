"""
This joins our AxesSpec model to matplotlib.axes.Axes. It is used by
bluesky_widgets.qt.figures and bluesky_widgets.jupyter.figures.
"""
import logging

from .models.plot_specs import AxesSpec, LineSpec, ImageStackSpec
from .models.utils import run_is_live_and_not_completed


class MatplotlibAxes:
    """
    Respond to changes in AxesSpec by manipulating matplotlib.axes.Axes.

    Note that while most view classes accept model as their only __init__
    parameter, this view class expects matplotlib.axes.Axes as well. If we
    follow the pattern used elsewhere in bluesky-widgets, we would want to
    receive only the model and to create matplotlib.axes.Axes internally in
    this class.

    The reason we break the pattern is pragmatic: matplotlib's
    plt.subplots(...) function is the easiest way to create a Figure and Axes
    with a nice layout, and it creates both Figure and Axes. So, this class
    receives pre-made Axes from the outside, ultimately via plt.subplots(...).
    """

    __slots__ = ()

    def __init__(self, model: AxesSpec, axes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.axes = axes

        axes.set_xlabel(model.x_label)
        axes.set_ylabel(model.y_label)

        # Use matplotlib's user-configurable ID so that we can look up the
        # AxesSpec from the axes if we need to.
        axes.set_gid(model.uuid)

        # Keep a reference to all types of artist here.
        self._artists = {}
        # And keep type-specific references in type-specific caches.
        self._lines = {}
        self._image_stacks = {}

        self.type_map = {
            LineSpec: self._lines,
            ImageStackSpec: self._image_stacks,
        }

        for line_spec in model.lines:
            self._add_line(line_spec)
        self.connect(model.lines.events.added, self._on_line_added)
        self.connect(model.lines.events.removed, self._on_artist_removed)
        self.connect(model.events.x_label, self._on_x_label_changed)
        self.connect(model.events.y_label, self._on_y_label_changed)

        for image_stack_spec in model.image_stacks:
            self._add_image_stack(image_stack_spec)
        self.connect(model.image_stacks.events.added, self._on_image_stack_added)
        self.connect(model.image_stacks.events.removed, self._on_artist_removed)

    def connect(self, emitter, callback):
        "The Qt view overwrites this with a threadsafe connect."
        emitter.connect(callback)

    def _on_x_label_changed(self, event):
        self.axes.set_xlabel(event.value)
        self._redraw()

    def _on_y_label_changed(self, event):
        self.axes.set_ylabel(event.value)
        self._redraw()

    def _on_line_added(self, event):
        line_spec = event.item
        self._add_line(line_spec)

    def _on_image_stack_added(self, event):
        image_stack_spec = event.item
        self._add_image_stack(image_stack_spec)

    def _add_line(self, line_spec):
        run = line_spec.run
        x, y = line_spec.func(run)

        # Initialize artist with currently-available data.
        (artist,) = self.axes.plot(x, y, label=line_spec.label, **line_spec.style)

        # If this is connected to a streaming data source and is not yet
        # complete, listen for updates.
        if run_is_live_and_not_completed(run):

            def update(event):
                x, y = line_spec.func(run)
                artist.set_data(x, y)
                self.axes.relim()  # Recompute data limits.
                self.axes.autoscale_view()  # Rescale the view using those new limits.
                self.axes.figure.canvas.draw_idle()

            self.connect(run.events.new_data, update)
            self.connect(
                run.events.completed,
                lambda event: run.events.new_data.disconnect(update),
            )

        self._add_artist(line_spec, artist)

    def _add_image_stack(self, image_stack_spec):
        run = image_stack_spec.run
        array = image_stack_spec.func(run)

        # Initialize artist with currently-available data.
        (artist,) = self.axes.imshow(array, **image_stack_spec.artist_kwargs)

        # If this is connected to a streaming data source and is not yet
        # complete, listen for updates.
        if hasattr(run, "events") and (run.metadata["stop"] is None):

            def update(event):
                array = image_stack_spec.func(run)
                artist.set_data(array)
                self.axes.relim()  # Recompute data limits.
                self.axes.autoscale_view()  # Rescale the view using those new limits.
                self.axes.figure.canvas.draw_idle()

            self.connect(run.events.new_data, update)
            self.connect(
                run.events.completed,
                lambda event: run.events.new_data.disconnect(update),
            )

        self._add_artist(image_stack_spec, artist)

    def _add_artist(self, artist_spec, artist):
        """
        This is called by methods line _add_line to perform generic setup.
        """
        # Track it as a generic artist cache and in a type-specific cache.
        self._artists[artist_spec.uuid] = artist
        self.type_map[type(artist_spec)][artist_spec.uuid] = artist
        # Use matplotlib's user-configurable ID so that we can look up the
        # ArtistSpec from the artist artist if we need to.
        artist.set_gid(artist_spec.uuid)

        # Listen for changes to label and style.
        self.connect(artist_spec.events.label, self._on_label_changed)
        self.connect(artist_spec.events.style_updated, self._on_style_updated)
        self._redraw()

    def _on_label_changed(self, event):
        artist_spec = event.artist_spec
        artist = self._artists[artist_spec.uuid]
        artist.set(label=event.value)
        self._redraw()

    def _on_style_updated(self, event):
        artist_spec = event.artist_spec
        artist = self._artists[artist_spec.uuid]
        artist.set(**event.update)
        self._redraw()

    def _on_artist_removed(self, event):
        artist_spec = event.item
        # Remove the artist from our caches.
        artist = self._artists.pop(artist_spec.uuid)
        self.type_map[type(artist_spec)].pop(artist_spec.uuid)
        # Remove it from the canvas.
        artist.remove()
        self._redraw()

    def _redraw(self):
        "Update the legend and redraw the canvas."
        self.axes.legend(loc="best")  # Update the legend.
        # Schedule matplotlib to redraw the canvas at the next opportunity, in
        # a threadsafe fashion.
        self.axes.figure.canvas.draw_idle()


def _quiet_mpl_noisy_logger():
    "Do not filter or silence it, but avoid defaulting to the logger of last resort."
    logger = logging.getLogger("matplotlib.legend")
    logger.addHandler(logging.NullHandler())


_quiet_mpl_noisy_logger()
