"""
This joins our AxesSpec model to matplotlib.axes.Axes. It is used by
bluesky_widgets.qt.viewer and bluesky_widgets.jupyter_viewer.
"""
import logging

from .models.plot_specs import AxesSpec, LineSpec


class Axes:
    "Respond to changes in AxesSpec by maniupatling matplotlib.axes.Axes."

    def __init__(self, model: AxesSpec, axes):
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

        self.type_map = {
            LineSpec: self._lines,
        }

        for line_spec in model.lines:
            self._add_line(line_spec)
        model.lines.events.added.connect(self._on_line_added)
        model.lines.events.removed.connect(self._on_artist_removed)

    def _on_line_added(self, event):
        line_spec = event.item
        self._add_line(line_spec)

    def _add_line(self, line_spec):
        run = line_spec.run
        x, y = line_spec.func(run)

        # Initialize artist with currently-available data.
        (artist,) = self.axes.plot(x, y, **line_spec.artist_kwargs)

        # If this is connected to a streaming data source and is not yet
        # complete, listen for updates.
        if hasattr(run, "events") and (run.metadata["stop"] is None):

            def update(event):
                x, y = line_spec.func(run)
                artist.set_data(x, y)
                self.axes.relim()  # Recompute data limits.
                self.axes.autoscale_view()  # Rescale the view using those new limits.
                self.axes.figure.canvas.draw_idle()

            run.events.new_data.connect(update)
            run.events.completed.connect(
                lambda event: run.events.new_data.disconnect(update)
            )

        self._add_artist(line_spec, artist)

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

        # Listen for changes to artist_kwargs.
        artist_spec.events.artist_kwargs_updated.connect(self._on_artist_kwargs_updated)
        self._redraw()

    def _on_artist_kwargs_updated(self, event):
        artist_spec = event.source
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
        self.axes.legend(loc="best")  # Update the legend.
        # Schedule matplotlib to redraw the canvas to at the next opportunity.
        self.axes.figure.canvas.draw_idle()


def _quiet_mpl_noisy_logger():
    "Do not filter or silence it, but avoid defaulting to the logger of last resort."
    logger = logging.getLogger("matplotlib.legend")
    logger.addHandler(logging.NullHandler())


_quiet_mpl_noisy_logger()
