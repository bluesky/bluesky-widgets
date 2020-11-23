"""
Models representing entities in a plot, including containers (Figure, Axes) and
artists (Line, Grid, Image).

We follow the pattern that parents know about their children but children do
not know about their parents: thus, Figures know about their Axes and Axes know
about their Artists.
"""
import collections
import uuid as uuid_module

from ..utils.event import EmitterGroup, Event
from ..utils.list import EventedList
from ..utils.dict_view import UpdateOnlyDict, DictView


class BaseSpec:
    "Just a class with a uuid attribute and some slots."
    __slots__ = ("_uuid", "events", "__weakref__")

    def __init__(self, uuid):
        if uuid is None:
            uuid = uuid_module.uuid4()
        self._uuid = uuid

    @property
    def uuid(self):
        return self._uuid


class FigureSpec(BaseSpec):
    """
    Describes a Figure

    Parameters
    ----------
    axes : Tuple[AxesSpec]
    title : String
        Figure title text
    uuid : UUID, optional
        Automatically assigned to provide a unique identifier for this Figure,
        used internally to track it.
    """

    __slots__ = ("_axes", "_title")

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
        "String for figure title. Settable."
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

    Paraemeters
    -----------
    lines : List[LineSpec], optional
    x_label: String, optional
        Text label for x axis
    y_label: String, optional
        Text label for y axis
    uuid : UUID, optional
        Automatically assigned to provide a unique identifier for this Figure,
        used internally to track it.

    Examples
    --------

    Note that plot entities like lines may be declared at init time:

    >>> axes = AxesSpec(lines=[LineSpec(...)])

    Or added later:

    >>> axes = AxesSpec()
    >>> axes.lines.append(LineSpec(...))

    Or a mix:

    >>> axes = AxesSpec(lines=[LineSpec(...)])
    >>> axes.lines.append(LineSpec(...))

    And they can be removed at any point:

    >>> del axes.lines[0]  # Remove the first one.
    >>> del axes.lines[-1]  # Remove the last one.
    >>> axes.lines.clear()  # Remove them all.

    They may be accessed by type

    >>> axes.lines  # all lines
    [LineSpec(...), LineSpec(...), ...]

    Or by label

    >>> axes.by_label["Scan 8"]  # list of all plot entities with this label
    [LineSpec(...)]  # typically contains just one element
    """

    __slots__ = ("_figure", "_artists", "_lines", "_images", "_x_label", "_y_label")

    def __init__(
        self, *, lines=None, images=None, x_label=None, y_label=None, uuid=None
    ):
        self._figure = None
        self._lines = LineSpecList(lines or [])
        self._images = ImageSpecList(images or [])
        # A colleciton of all artists, mappping UUID to object
        self._artists = {}
        self._x_label = x_label
        self._y_label = y_label
        self.events = EmitterGroup(source=self, x_label=Event, y_label=Event)
        super().__init__(uuid)
        self._lines.events.added.connect(self._on_artist_added)
        self._lines.events.removed.connect(self._on_artist_removed)
        self._images.events.added.connect(self._on_artist_added)
        self._images.events.removed.connect(self._on_artist_removed)

    @property
    def figure(self):
        """
        The Figure in which this Axes is located.

        See Also
        --------
        :meth:`set_figure`
        """
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
    def images(self):
        "List of ImageSpecs on these Axes. Mutable"
        return self._images

    @property
    def by_label(self):
        """
        Access artists as a read-only dict keyed by label.

        Since two artists are allowed to have the same label, the values are
        *lists*. In the common case, the list will have just one element.

        Examples
        --------

        Look up an object (e.g. a line) by its label and change its color.

        >>> spec = axes_spec.by_label["Scan 3"]
        >>> spec.style.update(color="red")
        """
        mapping = collections.defaultdict(list)
        for artist in self._artists.values():
            mapping[artist.label].append(artist)
        return DictView(mapping)

    @property
    def by_uuid(self):
        """
        Access artists as a read-only dict keyed by uuid.
        """
        # Return a copy to prohibit mutation of internal bookkeeping.
        return DictView(self._artists)

    @property
    def x_label(self):
        "String for x axes label. Settable."
        return self._x_label

    @x_label.setter
    def x_label(self, value):
        self._x_label = value
        self.events.x_label(value=value)

    @property
    def y_label(self):
        "String for y axes label. Settable."
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
            f"{self.__class__.__name__}(lines={self.lines!r}, "
            f"images={self.images!r}, "
            f"x_label={self.x_label!r}, y_label={self.y_label!r}, "
            f"uuid={self.uuid!r})"
        )


class ArtistSpec(BaseSpec):
    """
    Describes the data, computation, and style for an artist (plot element)

    func : callable
        Expected signature::

            func(run: BlueskyRun)

        The expected return type varies by artist.
    run : BlueskyRun
        Contains data to be visualized.
    label : String
        Label used in legend and for lookup by label on AxesSpec.
    style : Dict, optional
        Options passed through to plotting framework, such as ``color`` or
        ``label``.
    axes : AxesSpec, optional
        This may be specified here or set later using :meth:`set_axes`. Once
        specified, it cannot be changed.
    uuid : UUID, optional
        Automatically assigned to provide a unique identifier for this Figure,
        used internally to track it.
    """

    __slots__ = ("_func", "_run", "_label", "_style", "_axes")

    def __init__(self, func, run, label, style=None, axes=None, uuid=None):
        self._func = func
        self._run = run
        self._label = label
        self._style = UpdateOnlyDict(style or {})
        self._axes = axes
        self.events = EmitterGroup(source=self, label=Event, style_updated=Event)
        # Re-emit updates. It's important to re-emit (not just pass through)
        # because the consumer will need access to self.
        self._style.events.updated.connect(
            lambda event: self.events.style_updated(
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
        """
        The Axes on which this Artist is drawn.

        See Also
        --------
        :meth:`set_axes`
        """
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
    def label(self):
        "Label used in legend and for lookup by label on AxesSpec. Settable."
        return self._label

    @label.setter
    def label(self, value):
        self._label = str(value)
        self.events.label(value=value, artist_spec=self)

    @property
    def style(self):
        """
        Options passed to the artist.

        This *is* settable but it has to be done like:

        >>> spec.style.update({"color": "blue"})

        Attempts to modify the contents will be disallowed:

        >>> spec.style["color"] = blue  # TypeError!
        >>> del spec.style["color"]  # TypeError!
        """
        return self._style

    @style.setter
    def style(self, update):
        # Provide a more helpful error than the default,
        # AttributeError: can't set attribute.
        raise AttributeError(
            f"can't set attribute. Use style.update({update!r}) "
            f"instead of style = {update!r}."
        )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(func={self.func!r}, run={self.run!r}, "
            f"label={self.label!r}, style={self.style!r}, axes={self.axes!r}"
            f"uuid={self.uuid!r})"
        )


class LineSpec(ArtistSpec):
    """
    Describes the data, computation, and style for a line

    func : callable
        Expected signature::

            func(run: BlueskyRun) -> x: Array, y: Array

    run : BlueskyRun
        Contains data to be visualized.
    label : String
        Label used in legend and for lookup by label on AxesSpec.
    style : Dict, optional
        Options passed through to plotting framework, such as ``color`` or
        ``label``.
    axes : AxesSpec, optional
        This may be specified here or set later using :meth:`set_axes`. Once
        specified, it cannot be changed.
    uuid : UUID, optional
        Automatically assigned to provide a unique identifier for this Figure,
        used internally to track it.
    """

    __slots__ = ()


class ImageSpec(ArtistSpec):
    "Describes an image stack (both data and style)"


# EventedLists for each type of spec. We plan to add type-checking to these,
# hence a specific container for each.


class FigureSpecList(EventedList):
    __slots__ = ()


class AxesSpecList(EventedList):
    __slots__ = ()


class LineSpecList(EventedList):
    __slots__ = ()


class ImageSpecList(EventedList):
    __slots__ = ()
