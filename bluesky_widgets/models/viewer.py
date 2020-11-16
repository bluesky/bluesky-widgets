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
