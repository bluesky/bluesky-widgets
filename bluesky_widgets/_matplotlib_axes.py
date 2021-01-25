"""
This joins our Axes model to matplotlib.axes.Axes. It is used by
bluesky_widgets.qt.figures and bluesky_widgets.jupyter.figures.
"""
import functools
import logging

import matplotlib
import matplotlib.lines
import matplotlib.image

from .models.plot_specs import Axes, Line, Image


class _PatchedAxesImage(matplotlib.image.AxesImage):
    """
    AxesImage is an unusual Artist. Patch its API to me more like other Artitsts.

    - It does not accept data at __init__. Data must be added through a
      post-init method call.
    - Its set(...) method also does not accept data (?).
    """
    def __init__(self, *args, array, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_data(array)

        # TODO This is copied from imshow. How much of it do we want?
        # im.set_alpha(alpha)
        # if im.get_clip_path() is None:
        #     # image does not already have clipping set, clip to axes patch
        #     im.set_clip_path(self.patch)
        # im._scale_norm(norm, vmin, vmax)
        # im.set_url(url)

        # # update ax.dataLim, and, if autoscaling, set viewLim
        # # to tightly fit the image, regardless of dataLim.
        # im.set_extent(im.get_extent())

        # self.add_image(im)
        # return im

    def set(self, *, array=None, **kwargs):
        if array is not None:
            self.set_data(array)
        if kwargs:
            super().set(**kwargs)


class MatplotlibAxes:
    """
    Respond to changes in Axes by manipulating matplotlib.axes.Axes.

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
    def __init__(self, model: Axes, axes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.axes = axes

        # AxesImage *requires* Axes ax, so we define this mapping as an
        # instance attribute that can wrap self.axes.
        self.type_map = {
            Line: (matplotlib.lines.Line2D, {"x": "xdata", "y": "ydata"}),
            Image: (functools.partial(_PatchedAxesImage, ax=self.axes), {}),
        }

        # If we specify data limits and axes aspect and position, we have
        # overdetermined the system. When these are incompatible, we want
        # matplotlib to expand the data limts along one dimension rather than
        # disorting the boundaries of the axes (for example, creating a tall,
        # shinny axes box).
        self.axes.set_adjustable("datalim")

        axes.set_title(model.title)
        axes.set_xlabel(model.x_label)
        axes.set_ylabel(model.y_label)
        aspect = model.aspect or "auto"
        axes.set_aspect(aspect)
        if model.x_limits is not None:
            axes.set_xlim(model.x_limits)
        if model.y_limits is not None:
            axes.set_ylim(model.y_limits)

        # Use matplotlib's user-configurable ID so that we can look up the
        # Axes from the axes if we need to.
        axes.set_gid(model.uuid)

        # Keep a reference to all types of artist here.
        self._artists = {}

        for artist in model.artists:
            self._add_artist(artist)
        self.connect(model.artists.events.added, self._on_artist_spec_added)
        self.connect(model.artists.events.removed, self._on_artist_spec_removed)
        self.connect(model.events.title, self._on_title_changed)
        self.connect(model.events.x_label, self._on_x_label_changed)
        self.connect(model.events.y_label, self._on_y_label_changed)
        self.connect(model.events.aspect, self._on_aspect_changed)
        self.connect(model.events.x_limits, self._on_x_limits_changed)
        self.connect(model.events.y_limits, self._on_y_limits_changed)

    def connect(self, emitter, callback):
        """
        Add a callback to an emitter.

        This is exposed as a separate method so that The Qt view can override
        it this with a threadsafe connect.
        """
        emitter.connect(callback)

    def draw_idle(self):
        """
        Re-draw the figure when the UI is ready.

        This is exposed as a separate method so that it can be overriden with a
        more aggressive draw() for debugging in contexts where thread-safety
        is not a concern.
        """
        self.axes.figure.canvas.draw_idle()

    def _on_title_changed(self, event):
        self.axes.set_title(event.value)
        self._update_and_draw()

    def _on_x_label_changed(self, event):
        self.axes.set_xlabel(event.value)
        self._update_and_draw()

    def _on_y_label_changed(self, event):
        self.axes.set_ylabel(event.value)
        self._update_and_draw()

    def _on_aspect_changed(self, event):
        aspect = event.value or "auto"
        self.axes.set_aspect(aspect)
        self._update_and_draw()

    def _on_x_limits_changed(self, event):
        self.axes.set_xlim(event.value)
        self._update_and_draw()

    def _on_y_limits_changed(self, event):
        self.axes.set_ylim(event.value)
        self._update_and_draw()

    def _on_artist_spec_added(self, event):
        artist_spec = event.item
        self._add_artist(artist_spec)

    def _add_artist(self, artist_spec):
        """
        Add an artist.
        """
        # Initialize artist with currently-available data.
        artist_class, translation = self.type_map[type(artist_spec)]
        translated_kwargs = {}
        for k, v in artist_spec.update().items():
            translated_kwargs[translation.get(k, k)] = v
        artist = artist_class(
            label=artist_spec.label,
            **translated_kwargs,
            **artist_spec.style
        )

        if artist_spec.live:

            def update(event):
                translated_kwargs = {}
                for k, v in artist_spec.update().items():
                    translated_kwargs[translation.get(k, k)] = v
                artist.set(**translated_kwargs)
                self.axes.relim()  # Recompute data limits.
                self.axes.autoscale_view()  # Rescale the view using those new limits.
                self.draw_idle()

            self.connect(artist_spec.events.new_data, update)
            self.connect(
                artist_spec.events.completed,
                lambda event: artist_spec.events.new_data.disconnect(update),
            )

        # Track it as a generic artist cache and in a type-specific cache.
        self._artists[artist_spec.uuid] = artist
        # Use matplotlib's user-configurable ID so that we can look up the
        # ArtistSpec from the artist artist if we need to.
        artist.set_gid(artist_spec.uuid)
        # Listen for changes to label and style.
        self.connect(artist_spec.events.label, self._on_label_changed)
        self.connect(artist_spec.events.style_updated, self._on_style_updated)
        # Add artist to Axes.
        # TODO What happens with AxesImage here? It requires and receives the
        # Axes up front. Does it ignore this call?
        self.axes.add_artist(artist)
        self._update_and_draw()

    def _on_label_changed(self, event):
        artist_spec = event.artist_spec
        artist = self._artists[artist_spec.uuid]
        artist.set(label=event.value)
        self._update_and_draw()

    def _on_style_updated(self, event):
        artist_spec = event.artist_spec
        artist = self._artists[artist_spec.uuid]
        artist.set(**event.update)
        self._update_and_draw()

    def _on_artist_spec_removed(self, event):
        artist_spec = event.item
        # Remove the artist from our caches.
        artist = self._artists.pop(artist_spec.uuid)
        # Remove it from the canvas.
        artist.remove()
        self._update_and_draw()

    def _update_and_draw(self):
        "Update the legend and redraw the canvas."
        self.axes.legend(loc=1)  # Update the legend.
        self.draw_idle()  # Ask matplotlib to redraw the figure.


def _quiet_mpl_noisy_logger():
    "Do not filter or silence it, but avoid defaulting to the logger of last resort."
    logger = logging.getLogger("matplotlib.legend")
    logger.addHandler(logging.NullHandler())


_quiet_mpl_noisy_logger()
