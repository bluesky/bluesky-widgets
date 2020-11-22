"""
Models representing entities in a plot, including containers (Figure, Axes) and
artists (Line, Grid, ImageStack).

We follow the pattern that parents know about their children but children do
not know about their parents: thus, Figures know about their Axes and Axes know
about their Artists.
"""
import collections
import uuid as uuid_module

from ..utils.event import EmitterGroup, Event
from ..utils.list import EventedList
from ..utils.dict_view import UpdateOnlyDict


class BaseSpec:
    "Just a class with a uuid attribute."
    __slots__ = ()

    def __init__(self, uuid):
        if uuid is None:
            uuid = uuid_module.uuid4()
        self._uuid = uuid

    @property
    def uuid(self):
        return self._uuid


class FigureSpec(BaseSpec):
    "Describes a Figure"
    __slots__ = ()

    def __init__(self, axes, *, title, uuid=None):
        for ax in axes:
            ax.set_figure(self)
        self._axes = tuple(axes)
        self._title = title
        self.events = EmitterGroup(source=self, title=Event)
        super().__init__(uuid)

    @property
    def axes(self):
        """
        Tuple of AxesSpecs. Set at FigureSpec creation time and immutable.

        Why is it immutable? Because rearranging Axes to make room for a new
        one is currently painful to do in matplotlib. This constraint might be
        relaxed in the future if the situation improves in matplotlib or if
        support for other plotting frameworks is added to bluesky-widgets.
        """
        return self._axes

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
            f"{self.__class__.__name__}(axes={self.axes!r}, "
            f"title={self.title!r}, uuid={self.uuid!r})"
        )


class AxesSpec(BaseSpec):
    """
    Describes a set of Axes

    Note that lines may be declare at init time:

    >>> a = AxesSpec(lines=[LineSpec(...)])

    Or added later:

    >>> a = AxesSpec()
    >>> a.lines.append(LineSpec(...))

    Or a mix:

    >>> a = AxesSpec(lines=[LineSpec(...)])
    >>> a.lines.append(LineSpec(...))

    And they can be removed at any point:

    >>> del lines[0]  # Remove the first one.
    >>> del lines[-1]  # Remove the last one.
    >>> a.lines.clear()  # Remove them all.
    """
    __slots__ = ()

    def __init__(self, *, lines=None, x_label=None, y_label=None, uuid=None):
        self._figure = None
        self._lines = LineSpecList(lines or [])
        # A colleciton of all artists, mappping UUID to object
        self._artists = {}
        self._x_label = x_label
        self._y_label = y_label
        self.events = EmitterGroup(source=self, x_label=Event, y_label=Event)
        super().__init__(uuid)
        self._lines.events.added.connect(self._on_artist_added)
        self._lines.events.removed.connect(self._on_artist_removed)

    @property
    def figure(self):
        "The Figure in which this Axes is located."
        return self._figure

    def set_figure(self, figure):
        """
        This is called by FigureSpec when the Axes is added to it.

        It may only be called once.
        """
        if self._figure is not None:
            raise RuntimeError(
                f"Figure may only be set once. The Axes  {self} already belongs "
                f"to {self.figure} and thus cannot be added to {figure}."
            )
        self._figure = figure

    @property
    def lines(self):
        "List of LineSpecs on these Axes. Mutable."
        return self._lines

    @property
    def by_label(self):
        """
        Access artists as a dict keyed by label.

        Since two artists are allowed to have the same label, the values are
        *lists*. In the common case, the list will have just one element.

        Examples
        --------

        Look up an object (e.g. a line) by its label and change its color.

        >>> spec = axes_spec.by_label["Scan 3"]
        >>> spec.artist_kwargs = {"color": "red"}
        """
        mapping = collections.defaultdict(list)
        for artist in self._artists.values():
            label = artist.artist_kwargs.get("label")
            if label is not None:
                mapping[label].append(artist)
        return dict(mapping)

    @property
    def by_uuid(self):
        """
        Access artists as a dict keyed by uuid.
        """
        # Return a copy to prohibit mutation of internal bookkeeping.
        return dict(self._artists)

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
        self._artists[artist.uuid] = artist

    def _on_artist_removed(self, event):
        artist = event.item
        del self._artists[artist.uuid]

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(artists={self.lines!r}, "
            f"x_label={self.x_label!r}, y_label={self.y_label!r}, "
            f"uuid={self.uuid!r})"
        )


class ArtistSpec(BaseSpec):
    "Describes the data, computation, and style for an artist (plot element)"
    __slots__ = ()

    def __init__(self, func, run, artist_kwargs, axes=None, uuid=None):
        self._func = func
        self._run = run
        self._artist_kwargs = UpdateOnlyDict(artist_kwargs)
        self._axes = axes
        self.events = EmitterGroup(source=self, artist_kwargs_updated=Event)
        # Re-emit updates. It's important to re-emit (not just pass through)
        # because the consumer will need access to self.
        self._artist_kwargs.events.updated.connect(
            lambda event: self.events.artist_kwargs_updated(
                update=event.update, artist_spec=self
            )
        )
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

        >>> spec.artist_kwargs.update({"color": "blue"})

        Attempts to modify the contents will be disallowed:

        >>> spec.artist_kwargs["color"] = blue  # TypeError!
        >>> del spec.artist_kwargs["color"]  # TypeError!
        """
        return self._artist_kwargs

    @artist_kwargs.setter
    def artist_kwargs(self, update):
        # Provide a more helpful error than the default,
        # AttributeError: can't set attribute.
        raise AttributeError(
            f"can't set attribute. Use artist_kwargs.update({update!r}) "
            f"instead of artist_kwargs = {update!r}."
        )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(func={self.func!r}, run={self.run!r}, "
            f"artist_kwargs={self.artist_kwargs!r}, axes={self.axes!r}"
            f"uuid={self.uuid!r})"
        )


class LineSpec(ArtistSpec):
    "Describes a line (both data and style)"
    __slots__ = ()


# EventedLists for each type of spec. We plan to add type-checking to these,
# hence a specific container for each.


class FigureSpecList(EventedList):
    __slots__ = ()


class AxesSpecList(EventedList):
    __slots__ = ()


class LineSpecList(EventedList):
    __slots__ = ()
