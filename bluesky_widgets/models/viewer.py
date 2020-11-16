from collections import defaultdict, namedtuple
import uuid as uuid_module

# from ..utils.event import Event, EventEmitter
from ..utils.list import EventedList
from ..heuristics import LineSpec


class AxesSpecList(EventedList):
    ...


class LineSpecList(EventedList):
    ...


class GridSpecList(EventedList):
    ...


class ImageStackSpecList(EventedList):
    ...


class AxesList(EventedList):
    ...


class LineList(EventedList):
    ...


class GridList(EventedList):
    ...


class ImageStackList(EventedList):
    ...


class RunList(EventedList):
    ...


class PromptBuilderList(EventedList):
    ...


class StreamingBuilderList(EventedList):
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
        self.axes = AxesList()
        self.line_manager = LineManager()
        self.line_manager.line_specs.events.added.connect(self._on_line_spec_added)
        self.lines = LineList()
        self.prompt_builders = PromptBuilderList()
        self.prompt_builders.added.connect(self._on_prompt_builder_added)
        self.prompt_builders.removed.connect(self._on_prompt_builder_removed)
        self.streaming_builders = StreamingBuilderList()
        self.streaming_builders.added.connect(self._on_streaming_builder_added)
        self.streaming_builders.removed.connect(self._on_streaming_builder_removed)
        # Map Run uid to list of artifacts.
        self._ownership = defaultdict(list)

    @property
    def _axes_spec_to_axes(self):
        "Maps AxesSpec -> List[Axes]"
        # In the future we could construct and update this at write time rather
        # than reconstructing it at access time.
        d = defaultdict(list)
        for axes in self.axes:
            d[axes.spec].append(axes)
        return dict(d)

    def _on_run_added(self, event):
        "Callback run when a Run is added to self.runs"
        run = event.item
        # If the BlueskyRun is complete, feed the "prompt" builders
        # immediately.
        if run.metadata["stop"] is not None:
            self._feed_prompt_builders(run)
        # Otherwise, it is supports streaming, set up a callback to run the
        # "prompt" builders whenever it completes.
        elif hasattr(run, "events"):
            self.events.completed.connect(self._on_run_complete)

    def _on_run_complete(self, event):
        "Callback run with a streaming BlueskyRun is complete."
        for builder in self.prompt_builders:
            self._feed_prompt_builder(event.source, builder)
        self.events.completed.disconnect(self._on_run_complete)

    def _feed_prompt_builder(self, run, builder):
        "Pass a complete BlueskyRun to the prompt_builders."
        specs = builder(run)
        for spec in specs:
            if isinstance(spec, LineSpec):
                self.line_manager.line_specs.append(spec)
            else:
                raise TypeError("Unrecognized builder type")

    def _on_run_removed(self, event):
        "Callback run when a Run is removed from self.runs"
        run = event.item
        # Clean up all the lines for this Run.
        uid = run.metadata["start"]["uid"]
        for artifact in self._ownership[uid]:
            if artifact in self.lines:
                self.lines.remove(artifact)
        del self._ownership[uid]

    def _on_prompt_builder_added(self, event):
        builder = event.item
        for run in self.runs:
            # If the BlueskyRun is complete, feed the new "prompt" builder.
            if run.metadata["stop"] is not None:
                self._feed_prompt_builders(run, builder)

    def _on_prompt_builder_removed(self, event):
        # TODO Remove its artifacts? That may not be the user intention.
        ...

    def _on_streaming_builder_added(self, event):
        builder = event.item
        builder.events.lines.connect(self._on_line_spec_added)
        builder.events.grids.connect(self._on_grid_spec_added)
        builder.events.image_stacks.connect(self._on_image_stack_spec_added)

    def _on_streaming_builder_removed(self, event):
        builder = event.item
        builder.events.lines.disconnect(self._on_line_spec_added)
        builder.events.grids.disconnect(self._on_grid_spec_added)
        builder.events.image_stacks.disconnect(self._on_image_stack_spec_added)
        # TODO Remove its artifacts? That may not be the user intention.

    def _on_line_spec_added(self, event):
        line_spec = event.item
        # Do we need new Axes for this line?
        if self.line_manager.overplot and (
            line_spec.axes_spec in self._axes_spec_to_axes
        ):
            # Overplotting is turned on, and we have a matching
            # AxesSpec, so we will reuse the first matching Axes.
            axes = self._axes_spec_to_axes[line_spec.axes_spec][0]
        else:
            axes = new_axes(line_spec.axes_spec)
            self.axes.append(axes)
        line = new_line(line_spec, axes)
        self.lines.append(line)
        uid = line_spec.run.metadata["start"]["uid"]
        self._ownership[uid].append(line)

    def _on_grid_spec_added(self, event):
        ...

    def _on_image_stack_spec_added(self, event):
        ...
