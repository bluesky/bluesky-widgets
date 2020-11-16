from collections import defaultdict, namedtuple
import uuid as uuid_module

# from ..utils.event import Event, EventEmitter
from ..utils.list import EventedList


class AxesList(EventedList):
    ...


class LineList(EventedList):
    ...


class RunList(EventedList):
    ...


class ConsumerList(EventedList):
    ...


class HashByUUID:
    "Mixin class for providing a hash based on `uuid` attribute."

    def __hash__(self):
        # Expects to be mixed in with a class that exposes self.uuid: uuid.UUID
        return self.uuid.int


AxesSpec = namedtuple("AxesSpec", ["x_label", "y_label"])
"Describes axes"

_AxesTuple = namedtuple("Axes", ["uuid", "spec"])
Axes = type("Axes", (HashByUUID, _AxesTuple), {})

"Identifies a particular set of Axes"

LineSpec = namedtuple("LineSpec", ["func", "run", "axes_spec", "args", "kwargs"])
"Describes a line (both data and style)"

_LineTuple = namedtuple("Line", ["uuid", "spec", "axes"])
Line = type("Line", (HashByUUID, _LineTuple), {})
"Identfies a particular line"


def new_axes(spec):
    return Axes(uuid_module.uuid4(), spec)


def new_line(spec, axes):
    return Line(uuid_module.uuid4(), spec, axes)


def consumer(run):
    def func(run):
        ds = run.primary.read()
        return ds["motor"], ds["det"]

    axes_spec = AxesSpec("motor", "det")

    return [LineSpec(func, run, axes_spec, (), {})]


class Viewer:
    def __init__(self):
        self.runs = RunList()
        self.runs.events.added.connect(self._on_run_added)
        self.runs.events.removed.connect(self._on_run_removed)
        self.consumers = ConsumerList()
        self.axes = AxesList()  # contains Axes
        self.lines = LineList()  # contains Lines
        # Map Run uid to list of artifacts.
        self._ownership = defaultdict(list)
        self._overplot = False

    @property
    def overplot(self):
        """
        When adding lines, share axes where possible.
        """
        return self._overplot

    @overplot.setter
    def overplot(self, value):
        self._overplot = bool(value)

    def _on_run_added(self, event):
        run = event.item
        for consumer in self.consumers:
            line_specs = consumer(run)
            for line_spec in line_specs:
                axes = new_axes(line_spec.axes_spec)
                line = new_line(line_spec, axes)
                self.axes.append(line.axes)
                self.lines.append(line)
                uid = run.metadata["start"]["uid"]
                self._ownership[uid].append(line)

    def _on_run_removed(self, event):
        run = event.item
        # Clean up all the lines for this Run.
        uid = run.metadata["start"]["uid"]
        for artifact in self._ownership[uid]:
            if artifact in self.lines:
                self.lines.remove(artifact)
        del self._ownership[uid]
