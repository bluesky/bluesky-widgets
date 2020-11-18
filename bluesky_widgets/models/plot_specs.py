"""
Models representing entities in a plot, including containers (Figure, Axes) and
artists (Line, Grid, ImageStack).
"""
import uuid as uuid_module

from ..utils.event import EmitterGroup, Event
from ..utils.list import EventedList


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

    def __init__(self, axes_specs, title, uuid=None):
        self._axes_specs = axes_specs
        self._title = title
        self.events = EmitterGroup(source=self, title=Event)
        super().__init__(uuid)

    @property
    def axes_specs(self):
        "List of AxesSpecs. Set at FigureSpec creation time and immutable."
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
            f"{self.__class__.__name__}(axes_specs={self.axes_specs}, "
            f"title={self.title}, uuid={self.uuid})"
        )


class AxesSpec(BaseSpec):
    "Describes a set of Axes"

    def __init__(self, x_label, y_label, uuid=None):
        self._x_label = x_label
        self._y_label = y_label
        self.events = EmitterGroup(source=self, x_label=Event, y_label=Event)
        super().__init__(uuid)

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

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(x_label={self.x_label}, "
            f"y_label={self.y_label}, uuid={self.uuid})"
        )


class ArtistSpec(BaseSpec):
    "Describes the data, computation, and style for an artist (plot element)"

    def __init__(self, func, run, axes_spec, artist_kwargs, uuid=None):
        self._func = func
        self._run = run
        self._axes_spec = axes_spec
        self._artist_kwargs = artist_kwargs
        self.events = EmitterGroup(source=self, artist_kwargs=Event)
        super().__init__(uuid)

    @property
    def func(self):
        "Function that transforms BlueskyRun to plottble data. Immutable."
        return self._func

    @property
    def run(self):
        "BlueskyRun that is the data source. Immutable."
        return self._run

    @property
    def axes_spec(self):
        "AxesSpec for axes on which this artist is to be drawn. Immutable."
        return self._axes_spec

    @property
    def artist_kwargs(self):
        "Options passed to the artist."
        return self._artist_kwargs

    @artist_kwargs.setter
    def artist_kwargs(self, value):
        self._artist_kwargs = value
        self.events.artist_kwargs(value=value)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(func={self.func}, run={self.run}, "
            f"axes_spec={self.axes_spec}, artist_kwargs={self.artist_kwargs}, "
            f"uuid={self.uuid})"
        )


class LineSpec(ArtistSpec):
    "Describes a line (both data and style)"


class GridSpec(ArtistSpec):
    "Describes a gridded heat map (both data and style)"


class ImageStackSpec(ArtistSpec):
    "Describes an image stack (both data and style)"


# EventedLists for each type of spec. We plan to add type-checking to these,
# hence a specific container for each.


class FigureSpecList(EventedList):
    ...


class AxesSpecList(EventedList):
    ...


class LineSpecList(EventedList):
    ...


class GridSpecList(EventedList):
    ...


class ImageStackSpecList(EventedList):
    ...
