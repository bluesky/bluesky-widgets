from collections import namedtuple
from .utils.list import EventedList


AxesSpec = namedtuple("AxesSpec", ["x_label", "y_label"])
"Describes axes"

LineSpec = namedtuple("LineSpec", ["func", "run", "axes_spec", "args", "kwargs"])
"Describes a line (both data and style)"


class LineSpecList(EventedList):
    ...


class GridSpecList(EventedList):
    ...


class ImageStackList(EventedList):
    ...


def is_complete(run):
    return run.metadata["stop"] is not None


def prompt_line_builder(run):
    """
    This is a simple example.

    This makes a hard-coded assumption that the data has columns "motor" and
    "det" in the primary stream.
    """

    def func(run):
        ds = run.primary.read()
        return ds["motor"], ds["det"]

    axes_spec = AxesSpec("motor", "det")

    return [LineSpec(func, run, axes_spec, (), {})]


class StreamingPlotBuilder:
    """
    Base class for streaming builders
    """

    def __init__(self):
        self.lines = LineSpecList()
        self.grids = GridSpecList()
        self.image_stacks = ImageStackList()
        ...

    def __call__(self, run):
        # Implement this in the subclass.
        ...


class LastNLines:
    """
    Plot y vs x for the last N runs.
    """

    def __init__(self, N, x, y, stream_name="primary"):
        # Stash these and expose them as read-only properties.
        self._N = N
        self._x = x
        self._y = y
        self._stream_name = stream_name

    @property
    def N(self):
        return self._N

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def stream_name(self):
        return self._stream_name

    def __call__(self, run):
        # If necessary, removes lines to make room for the new one.
        while len(self.lines) >= self.N:
            self.lines.pop()

        stream_name = self.stream_name
        x = self.x
        y = self.y

        def func(run):
            ds = run[stream_name].to_dask()
            return ds[x], ds[y]

        axes_spec = AxesSpec(self.x, self.y)
        line_spec = LineSpec(func, run, axes_spec, (), {})

        self.lines.append(line_spec)
