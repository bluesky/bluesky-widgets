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


_AxesTuple = namedtuple("Axes", ["uuid", "spec"])
Axes = type("Axes", (HashByUUID, _AxesTuple), {})
"Identifies a particular set of Axes"

_LineTuple = namedtuple("Line", ["uuid", "spec", "axes"])
Line = type("Line", (HashByUUID, _LineTuple), {})
"Identfies a particular line"


def new_axes(spec):
    return Axes(uuid_module.uuid4(), spec)


def new_line(spec, axes):
    return Line(uuid_module.uuid4(), spec, axes)


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
    def _axes_spec_to_axes(self):
        "Maps AxesSpec -> List[Axes]"
        # In the future we could construct and update this at write time rather
        # than reconstructing it at access time.
        d = defaultdict(list)
        for axes in self.axes:
            d[axes.spec].append(axes)
        return dict(d)

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
                # Do we need new Axes for this line?
                if self.overplot and (line_spec.axes_spec in self._axes_spec_to_axes):
                    # Overplotting is turned on, and we have a matching
                    # AxesSpec, so we will reuse the first matching Axes.
                    axes = self._axes_spec_to_axes[line_spec.axes_spec][0]
                else:
                    axes = new_axes(line_spec.axes_spec)
                    self.axes.append(axes)
                line = new_line(line_spec, axes)
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
