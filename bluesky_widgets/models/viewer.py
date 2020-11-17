from collections import defaultdict, namedtuple
import uuid as uuid_module

# from ..utils.event import Event, EventEmitter
from ..utils.list import EventedList
from ..heuristics import (
    LineSpec,
    AxesSpec,
    FigureSpec,
    GridSpec,
    ImageStackSpec,
    LineSpecList,
    AxesSpecList,
    FigureSpecList,
    GridSpecList,
    ImageStackSpecList,
    StreamingPlotBuilder,
)


class RunList(EventedList):
    ...


class PromptBuilderList(EventedList):
    ...


class StreamingBuilderList(EventedList):
    ...


class Viewer:
    def __init__(self):
        # List of BlueskyRuns. These may be backed by data at rest or data
        # streaming off of a message bus.
        self.runs = RunList()

        # List of lightweight models (namedtuples) that represent axes and
        # various plot entities.
        self.figures = FigureSpecList()
        self.axes = AxesSpecList()
        self.lines = LineSpecList()
        self.grids = GridSpecList()
        self.image_stacks = ImageStackSpecList()

        # List of builders that will be handled a BlueskyRun when it is
        # complete.
        self.prompt_builders = PromptBuilderList()

        # List of builders that will respond to new data ina BlueskyRun in a
        # streaming fashion.
        self.streaming_builders = StreamingBuilderList()

        # Connect callbacks to react when the lists above change.
        self.runs.events.added.connect(self._on_run_added)
        self.runs.events.removed.connect(self._on_run_removed)
        self.prompt_builders.events.added.connect(self._on_prompt_builder_added)
        self.prompt_builders.events.removed.connect(self._on_prompt_builder_removed)
        self.streaming_builders.events.added.connect(self._on_streaming_builder_added)
        self.streaming_builders.events.removed.connect(
            self._on_streaming_builder_removed
        )

        # This utility is used to feed the output of prompt_builders into the
        # same system that processes streaming_builders.
        self._prompt_buidler_processor = PromptBuilderProcessor()

        # Map Run uid to list of artifacts.
        self._ownership = defaultdict(list)

    def _on_run_added(self, event):
        "Callback run when a Run is added to self.runs"
        run = event.item
        # Feed the steraming builders.
        for builder in self.streaming_builders:
            # This wires up callbacks that will observe updates in the run.
            # There is no return value to capture.
            # TODO Should this return a callable that we can use to *remove* the run?
            builder(run)
        # If the BlueskyRun is complete, feed the "prompt" builders
        # immediately.
        if run.metadata["stop"] is not None:
            for builder in self.prompt_builders:
                self._feed_prompt_builder(run, builder)
        # Otherwise, if it supports streaming, set up a callback to run the
        # "prompt" builders whenever it completes.
        elif hasattr(run, "events"):
            self.events.completed.connect(self._on_run_complete)

    def _on_run_complete(self, event):
        "Callback run with a streaming BlueskyRun is complete."
        for builder in self.prompt_builders:
            self._feed_prompt_builder(event.source, builder)
        self.events.completed.disconnect(self._on_run_complete)

    def _feed_prompt_builder(self, run, builder):
        "Pass a complete BlueskyRun to the prompt_builders and capture returns."
        specs = builder(run)
        for spec in specs:
            if isinstance(spec, LineSpec):
                self._on_new_line_spec(spec)
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
        builder.events.lines.connect(self._on_figure_spec_added)
        builder.events.lines.connect(self._on_axes_spec_added)
        builder.lines.events.added.connect(self._on_line_spec_added)
        builder.grids.events.added.connect(self._on_grid_spec_added)
        builder.image_stacks.events.added.connect(self._on_image_stack_spec_added)

        for run in self.runs:
            builder(run)

    def _on_streaming_builder_removed(self, event):
        builder = event.item
        builder.events.lines.disconnect(self._on_figure_spec_added)
        builder.events.lines.disconnect(self._on_axes_spec_added)
        builder.events.lines.disconnect(self._on_line_spec_added)
        builder.events.grids.disconnect(self._on_grid_spec_added)
        builder.events.image_stacks.disconnect(self._on_image_stack_spec_added)
        # TODO Remove its artifacts? That may not be the user intention.

    def _on_figure_spec_added(self, event):
        self.figures.append(event)

    def _on_axes_spec_added(self, event):
        self.axes.append(event)

    def _on_line_spec_added(self, event):
        line_spec = event.item
        if line_spec.axes_spec not in self.axes:
            raise RuntimeError("No Axes matching {axes_spec} exit. Cannot draw line.")
        self.lines.append(line)
        # TODO Track axes' lines so that removing axes removes lines.
        uid = line_spec.run.metadata["start"]["uid"]
        self._ownership[uid].append(line)

    def _on_grid_spec_added(self, event):
        ...

    def _on_image_stack_spec_added(self, event):
        ...


class PromptBuilderProcessor(StreamingPlotBuilder):
    def __init__(self):
        super().__init__(self)
        type_map = {
            FigureSpec: self.figures,
            AxesSpec: self.axes,
            LineSpec: self.lines,
            GridSpec: self.grids,
            ImageStackSpec: self.image_stacks,
        }

    def process_specs(self, specs):
        for spec in specs:
            try:
                list_ = self.type_map[type(spec)]
            except KeyError:
                raise TypeError(f"Unknown spec type {type(spec)}")
            list_.append(spec)
