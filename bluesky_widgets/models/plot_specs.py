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


class Figure(BaseSpec):
    """
    Describes a Figure

    Parameters
    ----------
    axes : Tuple[Axes]
    title : String
        Figure title text
    uuid : UUID, optional
        Automatically assigned to provide a unique identifier for this Figure,
        used internally to track it.
    short_title: String, optional
        Shorter figure title text, used in (for example) tab labels. Views
        should fall back on ``title`` if this is None.
    """

    __slots__ = ("_axes", "_title", "_short_title")

    def __init__(self, axes, *, title, uuid=None, short_title=None):
        for ax in axes:
            ax.set_figure(self)
        self._axes = tuple(axes)
        self._title = title
        self._short_title = short_title
        self.events = EmitterGroup(source=self, title=Event, short_title=Event)
        super().__init__(uuid)

    @property
    def axes(self):
        """
        Tuple of Axess. Set at Figure creation time and immutable.

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
        self.events.title(value=value, figure_spec=self)

    @property
    def short_title(self):
        "String for figure title tab label. Settable"
        return self._short_title

    @short_title.setter
    def short_title(self, value):
        self._short_title = value
        self.events.short_title(value=value, figure_spec=self)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(axes={self.axes!r}, "
            f"title={self.title!r}, short_title={self.short_title!r}, "
            f"uuid={self.uuid!r})"
        )


class Axes(BaseSpec):
    """
    Describes a set of Axes

    Parameters
    ----------
    Artists : List[Artist], optional
    title : String, optional
        Axes title text
    x_label : String, optional
        Text label for x axis
    y_label : String, optional
        Text label for y axis
    aspect : String or Float
        Passed through to :meth:`matplotlib.axes.Axes.imshow`
    x_limits : Tuple[Float]
        Limits of x axis
    y_limits : Tuple[Float]
        Limits of y axis
    uuid : UUID, optional
        Automatically assigned to provide a unique identifier for this Figure,
        used internally to track it.

    Examples
    --------

    Note that plot entities like lines may be declared at init time:

    >>> axes = Axes(artists=[Line(...)])

    Or added later:

    >>> axes = Axes()
    >>> axes.artists.append(Line(...))

    Or a mix:

    >>> axes = Axes(artists=[Line(...)])
    >>> axes.artists.append(Line(...))

    And they can be removed at any point:

    >>> del axes.artists[0]  # Remove the first one.
    >>> del axes.artists[-1]  # Remove the last one.
    >>> axes.artists.clear()  # Remove them all.

    They may be accessed by type

    >>> axes.artists  # all artists
    [Line(...), Line(...), ...]

    Or by label

    >>> axes.by_label["Scan 8"]  # list of all plot entities with this label
    [Line(...)]  # typically contains just one element
    """

    __slots__ = (
        "_figure",
        "_artists",
        "_title",
        "_x_label",
        "_y_label",
        "_aspect",
        "_x_limits",
        "_y_limits",
    )

    def __init__(
        self,
        *,
        artists=None,
        title=None,
        x_label=None,
        y_label=None,
        aspect=None,
        x_limits=None,
        y_limits=None,
        uuid=None,
    ):
        super().__init__(uuid)
        self._figure = None
        self._artists = ArtistList()
        self._title = title
        self._x_label = x_label
        self._y_label = y_label
        self._aspect = aspect
        self._x_limits = x_limits
        self._y_limits = y_limits
        self.events = EmitterGroup(
            source=self,
            figure=Event,
            title=Event,
            x_label=Event,
            y_label=Event,
            aspect=Event,
            x_limits=Event,
            y_limits=Event,
        )
        self.artists.events.adding.connect(self._on_artist_adding)
        self.artists.extend(artists or [])

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
        This is called by Figure when the Axes is added to it.

        It may only be called once.
        """
        if self._figure is not None:
            raise RuntimeError(
                f"Figure may only be set once. The Axes {self} already belongs "
                f"to {self.figure} and thus cannot be added to a new Figure."
            )
        self._figure = figure
        self.events.figure(value=figure)

    @property
    def artists(self):
        return self._artists

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
        for artist in self.artists:
            mapping[artist.label].append(artist)
        return DictView(dict(mapping))

    @property
    def by_uuid(self):
        """
        Access artists as a read-only dict keyed by uuid.
        """
        return DictView({artist.uuid: artist for artist in self.artists})

    def discard(self, artist):
        "Discard any Aritst."
        try:
            self.artists.remove(artist)
        except ValueError:
            pass

    def remove(self, artist):
        "Remove any Aritst."
        self.artists.remove(artist)

    @property
    def title(self):
        "String for figure title. Settable"
        return self._title

    @title.setter
    def title(self, value):
        self._title = value
        self.events.title(value=value)

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

    @property
    def aspect(self):
        "String or Float for aspect. Settable"
        return self._aspect

    @aspect.setter
    def aspect(self, value):
        self._aspect = value
        self.events.aspect(value=value)

    @property
    def x_limits(self):
        "Float for limits of x axis. Settable"
        return self._x_limits

    @x_limits.setter
    def x_limits(self, value):
        self._x_limits = value
        self.events.x_limits(value=value)

    @property
    def y_limits(self):
        "Float for limits of y axis. Settable"
        return self._y_limits

    @y_limits.setter
    def y_limits(self, value):
        self._y_limits = value
        self.events.y_limits(value=value)

    def _on_artist_adding(self, event):
        # This is called when the artist is *about* to be added to self.artists.
        # Set its axes to self. If it *already* has Axes this will raise and
        # the Axes will not be added.
        artist = event.item
        artist.set_axes(self)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(artists={self.artists!r}, "
            f"title={self.title!r},"
            f"x_label={self.x_label!r}, y_label={self.y_label!r}, "
            f"aspect={self.aspect!r}, x_limits={self.x_limits!r}, "
            f"y_limits={self.y_limits!r}, uuid={self.uuid!r})"
        )


class ArtistSpec(BaseSpec):
    """
    Describes the data, computation, and style for an artist (plot element)

    update : callable
        Expected signature::

            func() -> Dict

        Where Dict contains parameters expected by the specific Artist
    label : String
        Label used in legend and for lookup by label on Axes.
    style : Dict, optional
        Options passed through to plotting framework, such as ``color`` or
        ``label``.
    axes : Axes, optional
        This may be specified here or set later using :meth:`set_axes`. Once
        specified, it cannot be changed.
    live : Boolean, optional
        Listen for future updates.
    uuid : UUID, optional
        Automatically assigned to provide a unique identifier for this Figure,
        used internally to track it.
    """

    __slots__ = ("_live", "_update", "_label", "_style", "_axes")

    def __init__(self, update, *, label, style=None, axes=None, live=True, uuid=None):
        self._update = update
        self._label = label
        self._style = UpdateOnlyDict(style or {})
        self._axes = axes
        self._live = live
        self.events = EmitterGroup(
            source=self,
            label=Event,
            new_data=Event,
            completed=Event,
            style_updated=Event,
        )
        # Re-emit updates. It's important to re-emit (not just pass through)
        # because the consumer will need access to self.
        self._style.events.updated.connect(
            lambda event: self.events.style_updated(update=event.update, artist_spec=self)
        )
        super().__init__(uuid)

    @property
    def update(self):
        return self._update

    @property
    def live(self):
        return self._live

    def on_completed(self, event):
        self._live = False

    @classmethod
    def from_run(cls, transform, run, label, style=None, axes=None, uuid=None):
        """
        Construct a line representing data from one BlueskyRun.

        transform : callable
            Expected signature::

                func(run: BlueskyRun)

            The expected return type varies by artist.
        run : BlueskyRun
            Contains data to be visualized.
        label : String
            Label used in legend and for lookup by label on Axes.
        style : Dict, optional
            Options passed through to plotting framework, such as ``color`` or
            ``label``.
        axes : Axes, optional
            This may be specified here or set later using :meth:`set_axes`. Once
            specified, it cannot be changed.
        uuid : UUID, optional
            Automatically assigned to provide a unique identifier for this Figure,
            used internally to track it.
        """
        # Isolating bluesky-aware stuff here, including this import.
        from .utils import run_is_live_and_not_completed

        def update():
            return transform(run)

        live = run_is_live_and_not_completed(run)
        line = cls(update, label=label, style=style, live=live)
        if live:
            run.events.new_data.connect(line.events.new_data)
            run.events.completed.connect(line.events.completed)
        return line

    def set_axes(self, axes):
        """
        This is called by Axes when the Artist is added to it.

        It may only be called once.
        """
        if self._axes is not None:
            raise AxesAlreadySet(
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
    def label(self):
        "Label used in legend and for lookup by label on Axes. Settable."
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
        raise AttributeError(f"can't set attribute. Use style.update({update!r}) instead of style = {update!r}.")

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(update={self.update!r}"
            f"label={self.label!r}, style={self.style!r}, axes={self.axes!r}"
            f"uuid={self.uuid!r})"
        )


class Line(ArtistSpec):
    """
    Describes the data, computation, and style for a line

    func : callable
        Expected signature::

            func(run: BlueskyRun) -> x: Array, y: Array

    run : BlueskyRun
        Contains data to be visualized.
    label : String
        Label used in legend and for lookup by label on Axes.
    style : Dict, optional
        Options passed through to plotting framework, such as ``color`` or
        ``label``.
    axes : Axes, optional
        This may be specified here or set later using :meth:`set_axes`. Once
        specified, it cannot be changed.
    uuid : UUID, optional
        Automatically assigned to provide a unique identifier for this Figure,
        used internally to track it.
    """

    __slots__ = ()


class Image(ArtistSpec):
    "Describes an image (both data and style)"


# EventedLists for each type of spec. We plan to add type-checking to these,
# hence a specific container for each.


class FigureList(EventedList):
    __slots__ = ("_active_index",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active_index = None
        self.events.add(active_index=Event)

    @property
    def active_index(self):
        "Return the index of the active figure."
        return self._active_index

    @active_index.setter
    def active_index(self, value):
        self._active_index = value
        self.events.active_index(value=value)


class AxesList(EventedList):
    __slots__ = ()


class ArtistList(EventedList):
    __slots__ = ()


class AxesAlreadySet(RuntimeError):
    pass
