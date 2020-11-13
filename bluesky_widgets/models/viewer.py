from collections import defaultdict, namedtuple

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
        self._ownership = defaultdict(set)

    def _on_run_added(self, event):
        run = event.item
        for consumer in self.consumers:
            lines = consumer(run)
            for line in lines:
                if line.axes not in self.axes:
                    self.axes.append(line.axes)
                self.lines.append(line)
                # self._ownership[run].add(line)

    def _on_run_removed(self, event):
        run = event.item
        # Clean up all the lines for this Run.
        for line in self._owernship[run]:
            if line in self.lines:
                self.lines.remove(line)
        self._ownership.pop(run)
