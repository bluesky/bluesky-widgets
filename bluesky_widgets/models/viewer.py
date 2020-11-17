from collections import defaultdict
import weakref

# from ..utils.event import Event, EventEmitter
from ..utils.list import EventedList
from ..heuristics import (
    LineSpec,
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

        # List of lightweight models (namedtuples) that represent various plot
        # entities.
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
        self._prompt_builder_processor = _PromptBuilderProcessor()
        self._prompt_builder_processor.figures.events.added.connect(
            self._on_figure_spec_added_to_builder
        )
        self._prompt_builder_processor.figures.events.removed.connect(
            self._on_figure_spec_removed_from_builder
        )
        self._prompt_builder_processor.lines.events.added.connect(
            self._on_line_spec_added_to_builder
        )
        self._prompt_builder_processor.lines.events.removed.connect(
            self._on_line_spec_removed_from_builder
        )
        self._prompt_builder_processor.grids.events.added.connect(
            self._on_grid_spec_added_to_builder
        )
        self._prompt_builder_processor.grids.events.removed.connect(
            self._on_grid_spec_removed_from_builder
        )
        self._prompt_builder_processor.image_stacks.events.added.connect(
            self._on_image_stack_spec_added_to_builder
        )
        self._prompt_builder_processor.image_stacks.events.removed.connect(
            self._on_image_stack_spec_removed_from_builder
        )

        self.figures.events.added.connect(self._on_figure_spec_added_to_viewer)
        self.figures.events.removed.connect(self._on_figure_spec_removed_from_viewer)
        self.lines.events.added.connect(self._on_line_spec_added_to_viewer)
        self.lines.events.removed.connect(self._on_line_spec_removed_from_viewer)

        # These caches are used to clean up.
        # Map Axes UUID to FigureSpec.
        self._axes_to_figure = {}
        # Map Run uid to list of artifacts.
        self._run_ownership = defaultdict(list)
        # Map FigureSpec UUID to list of artifacts.
        self._figure_ownership = defaultdict(list)
        # Map artifacts' UUID to the EventedList that owns it.
        self._builder_ownership = weakref.WeakValueDictionary()

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
                self._prompt_builder_processor.process_specs(builder(run))
        # Otherwise, if it supports streaming, set up a callback to run the
        # "prompt" builders whenever it completes.
        elif hasattr(run, "events"):
            self.events.completed.connect(self._on_run_complete)

    def _on_run_complete(self, event):
        "Callback run with a streaming BlueskyRun is complete."
        for builder in self.prompt_builders:
            self._prompt_builder_processor.process_specs(builder(event.run))
        self.events.completed.disconnect(self._on_run_complete)

    def _on_run_removed(self, event):
        "Callback run when a Run is removed from self.runs"
        run = event.item
        # Clean up all the lines for this Run.
        uid = run.metadata["start"]["uid"]
        for artifact in self._run_ownership[uid]:
            if artifact in self.lines:
                self.lines.remove(artifact)
        del self._run_ownership[uid]

    def _on_prompt_builder_added(self, event):
        builder = event.item
        for run in self.runs:
            # If the BlueskyRun is complete, feed the new "prompt" builder.
            if run.metadata["stop"] is not None:
                self._prompt_builder_processor.process_specs(builder(run))

    def _on_prompt_builder_removed(self, event):
        # TODO Remove its artifacts? That may not be the user intention.
        ...

    def _on_streaming_builder_added(self, event):
        builder = event.item
        # Add any specs that the Builder already has.
        self.figures.extend(builder.figures)
        self.lines.extend(builder.lines)
        self.grids.extend(builder.grids)
        self.image_stacks.extend(builder.image_stacks)
        # Listen for updates to the Builder's lists of specs.
        builder.figures.events.added.connect(self._on_figure_spec_added_to_builder)
        builder.lines.events.added.connect(self._on_line_spec_added_to_builder)
        builder.grids.events.added.connect(self._on_grid_spec_added_to_builder)
        builder.image_stacks.events.added.connect(
            self._on_image_stack_spec_added_to_builder
        )
        builder.figures.events.removed.connect(
            self._on_figure_spec_removed_from_builder
        )
        builder.lines.events.removed.connect(self._on_line_spec_removed_from_builder)
        builder.grids.events.removed.connect(self._on_grid_spec_removed_from_builder)
        builder.image_stacks.events.removed.connect(
            self._on_image_stack_spec_removed_from_builder
        )
        # Feed the builder any Runs that we are already viewing.
        for run in self.runs:
            builder(run)

    def _on_streaming_builder_removed(self, event):
        builder = event.item
        builder.figures.events.added.disconnect(self._on_figure_spec_added_to_builder)
        builder.lines.events.added.disconnect(self._on_line_spec_added_to_builder)
        builder.grids.events.added.disconnect(self._on_grid_spec_added_to_builder)
        builder.image_stacks.events.added.disconnect(
            self._on_image_stack_spec_added_to_builder
        )
        builder.figures.events.removed.disconnect(
            self._on_figure_spec_removed_from_builder
        )
        builder.lines.events.removed.disconnect(self._on_line_spec_removed_from_builder)
        builder.grids.events.removed.disconnect(self._on_grid_spec_removed_from_builder)
        builder.image_stacks.events.removed.disconnect(
            self._on_image_stack_spec_removed_from_builder
        )
        # Intentionally leave the builder's artifacts behind.
        # Removing the builder means, "Do not make any more of these." It does
        # not mean, "Remove all its prior work."

    def _on_figure_spec_added_to_builder(self, event):
        # Add it to the Viewer as well.
        self.figures.append(event.item)

    def _on_figure_spec_removed_from_builder(self, event):
        # Ignore this. Builders are not allowed to remove figures from the
        # view, because figures are containers (potentially) shared by multiple
        # builders. Only the Viewer can initiate the removal of a figure.
        pass

    def _on_figure_spec_added_to_viewer(self, event):
        # Add all the Figure's Axes to the Viewer.
        figure_spec = event.item
        for axes_spec in figure_spec.axes_specs:
            self._axes_to_figure[axes_spec.uuid] = figure_spec
        self.axes.extend(event.item.axes_specs)

    def _on_figure_spec_removed_from_viewer(self, event):
        # Remove all the Figure's Axes from the Viewer.
        figure_spec = event.item
        for axes_spec in figure_spec.axes_specs:
            self.axes.remove(axes_spec)
        # Remove the Figure from any Builders that reference it.
        for builder in self.streaming_builders:
            j = 0
            for i, figure_spec_ in list(enumerate(builder.figures)):
                if figure_spec_.uuid == figure_spec.uuid:
                    del builder.figures[i - j]
                    j += 1
        # Clean up artifacts associated with this Figure.
        for artifact in self._figure_ownership[figure_spec.uuid]:
            if artifact in self.lines:
                self.lines.remove(artifact)
        # Clean up caches.
        del self._figure_ownership[figure_spec.uuid]
        for axes_spec in figure_spec.axes_specs:
            del self._axes_to_figure[axes_spec.uuid]

    def _on_line_spec_added_to_builder(self, event):
        # Add it to the Viewer as well, but check first that the Axes exist.
        line_spec = event.item
        if line_spec.axes_spec not in self.axes:
            raise RuntimeError(
                f"No FigureSpec with Axes matching {line_spec.axes_spec}. Cannot draw line."
            )
        self._builder_ownership[line_spec.uuid] = event.source
        self.lines.append(line_spec)

    def _on_line_spec_added_to_viewer(self, event):
        # Track the Run, Figure, and Builder this is associated with.
        line_spec = event.item
        run_uid = line_spec.run.metadata["start"]["uid"]
        self._run_ownership[run_uid].append(line_spec)
        figure_spec = self._axes_to_figure[line_spec.axes_spec.uuid]
        self._figure_ownership[figure_spec.uuid].append(line_spec)

    def _on_line_spec_removed_from_builder(self, event):
        # Remove it from the Viewer as well.
        line_spec = event.item
        self.lines.remove(line_spec)
        uid = line_spec.run.metadata["start"]["uid"]
        self._run_ownership[uid].remove(line_spec)

    def _on_line_spec_removed_from_viewer(self, event):
        # Remove it from the Builder as well.
        line_spec = event.item
        try:
            list_ = self._builder_ownership[line_spec.uuid]
        except KeyError:
            # The Builder is gone. Do nothing.
            return
        # Avoid a loop.
        list_.events.removed.block(callback=self._on_line_spec_removed_from_builder)
        try:
            list_.remove(line_spec)
        except ValueError:
            # The Builder has already "forgotten" this line (i.e. removed it
            # but intentionally did not notify the Viewer).
            pass
        finally:
            list_.events.removed.unblock(
                callback=self._on_line_spec_removed_from_builder
            )

    def _on_grid_spec_added_to_builder(self, event):
        ...

    def _on_grid_spec_removed_from_builder(self, event):
        ...

    def _on_image_stack_spec_added_to_builder(self, event):
        ...

    def _on_image_stack_spec_removed_from_builder(self, event):
        ...


class _PromptBuilderProcessor(StreamingPlotBuilder):
    """
    This wraps a "prompt builder" (simple function) in StreamingPlotBuilder.
    """

    def __init__(self):
        super().__init__()
        # Map which EventedList each type should go to.
        self.type_map = {
            FigureSpec: self.figures,
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
