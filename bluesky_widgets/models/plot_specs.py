"""
Models representing entities in a plot, including containers (Figure, Axes) and
artists (Line, Grid, ImageStack).

We follow the pattern that parents know about their children but children do
not know about their parents: thus, Figures know about their Axes and Axes know
about their Artists.
"""
import uuid as uuid_module

from ..utils.event import EmitterGroup, Event
from ..utils.list import EventedList
from ..utils.dict_view import DictView


class BaseSpec:
    "Just a class with a uuid attribute."

    def __init__(self, uuid):
        if uuid is None:
            uuid = uuid_module.uuid4()
        self._uuid = uuid

    @property
    def uuid(self):
        return self._uuid


class FigureSpec(BaseSpec):
    "Describes a Figure"

    def __init__(self, axes_specs, *, title, uuid=None):
        self._axes_specs = axes_specs
        self._title = title
        self.events = EmitterGroup(source=self, title=Event)
        super().__init__(uuid)

    @property
    def axes_specs(self):
        """
        List of AxesSpecs. Set at FigureSpec creation time and immutable.

        Why is it immutable? Because rearranging Axes to make room for a new
        one is currently painful to do in matplotlib. This constraint might be
        relaxed in the future if the situation improves in matplotlib or if
        support for other plotting frameworks is added to bluesky-widgets.
        """
        return self._axes_specs

    @property
    def title(self):
        "String for figure title"
        return self._title

    @title.setter
    def title(self, value):
        self._title = value
        self.events.title(value=value)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(axes_specs={self.axes_specs!r}, "
            f"title={self.title!r}, uuid={self.uuid!r})"
        )


class AxesSpec(BaseSpec):
    "Describes a set of Axes"

    def __init__(self, lines, *, x_label, y_label, uuid=None):
        self._lines = LineSpecList()
        self._x_label = x_label
        self._y_label = y_label
        self.events = EmitterGroup(source=self, x_label=Event, y_label=Event)
        super().__init__(uuid)
        self._lines.events.added.connect(self._on_artist_added)

    @property
    def lines(self):
        "List of LineSpecs on these Axes. Mutable."
        return self._lines

    @property
    def x_label(self):
        "String for x axes label."
        return self._x_label

    @x_label.setter
    def x_label(self, value):
        self._x_label = value
        self.events.x_label(value=value)

    @property
    def y_label(self):
        "String for y axes label."
        return self._y_label

    @y_label.setter
    def y_label(self, value):
        self._y_label = value
        self.events.y_label(value=value)

    def _on_artist_added(self, event):
        artist = event.item
        artist.set_axes(self)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(artists={self._artists!r}, "
            f"x_label={self.x_label!r}, y_label={self.y_label!r}, "
            f"uuid={self.uuid!r})"
        )


class ArtistSpec(BaseSpec):
    "Describes the data, computation, and style for an artist (plot element)"

    def __init__(self, func, run, artist_kwargs, axes=None, uuid=None):
        self._func = func
        self._run = run
        self._artist_kwargs = artist_kwargs
        self._axes = axes
        self.events = EmitterGroup(source=self, artist_kwargs=Event)
        super().__init__(uuid)

    def set_axes(self, axes):
        """
        This is called by AxesSpec when the Artist is added to it.

        It may only be called once.
        """
        if self._axes is not None:
            raise RuntimeError(
                f"Axes may only be set once. The artist {self} already belongs "
                f"to {self.axes} and thus cannot be added to {axes}."
            )
        self._axes = axes

    @property
    def axes(self):
        "The Axes on which this Artist is drawn."
        return self._axes

    @property
    def func(self):
        "Function that transforms BlueskyRun to plottble data. Immutable."
        return self._func

    @property
    def run(self):
        "BlueskyRun that is the data source. Immutable."
        return self._run

    @property
    def artist_kwargs(self):
        """
        Options passed to the artist.

        This *is* settable but it has to be done like:

        >>> spec.artist_kwargs = {"color": "blue"}

        Attempts to modify the contents will be disallowed:

        >>> spec.artist_kwargs["color"] = blue  # TypeError!

        because such changes would be unobservable.
        """
        return DictView(self._artist_kwargs)  # a read-only dict

    @artist_kwargs.setter
    def artist_kwargs(self, value):
        self._artist_kwargs = value
        self.events.artist_kwargs(value=value)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(func={self.func!r}, run={self.run!r}, "
            f"artist_kwargs={self.artist_kwargs!r}, axes={self.axes!r}"
            f"uuid={self.uuid!r})"
        )


class LineSpec(ArtistSpec):
    "Describes a line (both data and style)"


# EventedLists for each type of spec. We plan to add type-checking to these,
# hence a specific container for each.


class FigureSpecList(EventedList):
    ...


class AxesSpecList(EventedList):
    ...


class LineSpecList(EventedList):
    ...
