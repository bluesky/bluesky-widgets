from collections import defaultdict, namedtuple
import dataclasses
import typing
import uuid as uuid_module

# from ..utils.event import Event, EventEmitter
from ..utils.list import ListModel


class AxesList(ListModel):
    ...


class LineList(ListModel):
    ...


class RunList(ListModel):
    ...


class ConsumerList(ListModel):
    ...


AxesSpec = namedtuple("AxesSpec", ["x_label", "y_label"])
LineSpec = namedtuple("LineSpec", ["func", "run", "axes", "args", "kwargs"])


@dataclasses.dataclass(frozen=True)
class Spec:
    uuid: uuid_module.UUID = dataclasses.field(init=False)

    def __post_init__(self):
        # Setting an attribute on a frozen dataclass requires an invasive
        # operation.
        object.__setattr__(self, "uuid", uuid_module.uuid4())

    def __hash__(self):
        return self.uuid.int


@dataclasses.dataclass(frozen=True)
class AxesSpec(Spec):
    """
    Specify a set of axes.

    The names here are targetting matplotlib.axes.Axes but could in principle
    be used by a view that uses a different plotting library.
    """
    x_label: str
    y_label: str

    def __hash__(self):
        # The dataclass decorator overrides the implementation in the base
        # class if __hash__ is not explicitly defined in this class.
        return self.uuid.int


@dataclasses.dataclass(frozen=True)
class LineSpec(Spec):
    """
    Specify how to extract data for and stylize a line.
    """
    func: callable
    run: typing.Any  # may be bluesky_live or databroker BlueskyRun
    axes: AxesSpec
    args: tuple
    kwargs: dict  # DANGER: This ought to be a frozendict.

    def __hash__(self):
        # The dataclass decorator overrides the implementation in the base
        # class if __hash__ is not explicitly defined in this class.
        return self.uuid.int


def consumer(run):
    def func(run):
        ds = run.primary.read()
        return ds["motor"], ds["det"]

    axes = AxesSpec("motor", "det")

    return [LineSpec(func, run, axes, (), {})]


class Viewer:
    def __init__(self):
        self.runs = RunList()
        self.runs.events.added.connect(self._on_run_added)
        self.runs.events.removed.connect(self._on_run_removed)
        self.consumers = ConsumerList()
        self.axes = AxesList()
        self.lines = LineList()
        # Map Run uid to list of artifacts.
        self._ownership = defaultdict(list)

    def _on_run_added(self, event):
        run = event.item
        for consumer in self.consumers:
            lines = consumer(run)
            for line in lines:
                if line.axes not in self.axes:
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
