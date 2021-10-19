from warnings import warn

from ..plot_builders import Lines
from ..plot_specs import Figure, Axes
from .._heuristics import hinted_fields
from ._base import AutoPlotter


class AutoLines(AutoPlotter):
    """
    Construct figures with line plots automatically.

    The decision of which lines to plot is based on metadata and data shape.

    Examples
    --------

    >>> model = AutoLines()
    >>> from bluesky_widgets.jupyter.figures import JupyterFigures
    >>> view = JupyterFigures(model.figures)
    >>> model.add_run(run)
    """

    def __init__(self, *, max_runs=None):
        super().__init__()
        # Map (stream_name, x, tuple_of_tuple_of_ys) to line of Lines instances for each group of y.
        self._lines_instances = {}
        self._max_runs = max_runs
        self.figures.events.removed.connect(self._on_figure_removed)

    @property
    def max_runs(self):
        return self._max_runs

    @max_runs.setter
    def max_runs(self, value):
        if value is not None:
            for builders in self._lines_instances.values():
                for builder in builders:
                    builder.max_runs = value
        self._max_runs = value

    def _on_figure_removed(self, event):
        super()._on_figure_removed(event)
        figure = event.item
        for key, plot_builders in self._lines_instances.items():
            for plot_builder in plot_builders:
                if figure == plot_builder.figure:
                    key_to_remove = key
        self._lines_instances.pop(key_to_remove)

    def handle_new_stream(self, run, stream_name, **kwargs):
        """
        This is used internally and should not be called directly by user code.

        Given a run and stream name, add or update figures with line plots.

        Parameters
        ----------
        run : BlueskyRun
        stream_name : String
        """
        omit_single_point_plot = False
        cleanup_motor_heuristic = False
        start_doc = run.metadata["start"]
        plan_hints = start_doc.get("hints", {})

        # Prepare a guess about the dimensions (independent variables) in case
        # we need it.
        motors = start_doc.get("motors")
        if motors is not None:
            GUESS = [([motor], "primary") for motor in motors]
        else:
            GUESS = [(["time"], "primary")]

        # Ues the guess if there is not hint about dimensions.
        dimensions = plan_hints.get("dimensions")
        if dimensions is None:
            cleanup_motor_heuristic = True
            dimensions = GUESS

        # We can only cope with all the dimensions belonging to the same
        # stream unless we resample. We are not doing to handle that yet.
        if len(set(d[1] for d in dimensions)) != 1:
            cleanup_motor_heuristic = True
            dimensions = GUESS  # Fall back on our GUESS.
            warn("We are ignoring the dimensions hinted because we cannot combine streams.")

        # for each dimension, choose one field only
        # the plan can supply a list of fields. It's assumed the first
        # of the list is always the one plotted against
        dim_fields = [fields[0] for fields, stream_name in dimensions]

        # make distinction between flattened fields and plotted fields
        # motivation for this is that when plotting, we find dependent variable
        # by finding elements that are not independent variables
        all_dim_fields = [field for fields, stream_name in dimensions for field in fields]

        _, dim_stream = dimensions[0]

        # We only care about the first descriptor because we are not referencing
        # configuration.
        stream = run[stream_name]
        descriptor = stream._descriptors[0]  # HACK!

        columns = hinted_fields(descriptor)

        # ## This deals with old descriptoruments. ## #

        if stream_name == "primary" and cleanup_motor_heuristic:
            # We stashed object names in dim_fields, which we now need to
            # look up the actual fields for.
            cleanup_motor_heuristic = False
            fixed_dim_fields = []
            for obj_name in dim_fields:
                # Special case: 'time' can be a dim_field, but it's not an
                # object name. Just add it directly to the list of fields.
                if obj_name == "time":
                    fixed_dim_fields.append("time")
                    continue
                try:
                    fields = descriptor.get("hints", {}).get(obj_name, {})["fields"]
                except KeyError:
                    fields = descriptor["object_keys"][obj_name]
                fixed_dim_fields.extend(fields)
            dim_fields = fixed_dim_fields

        # Ensure that no independent variables ('dimensions') are
        # duplicated here.
        columns = [c for c in columns if c not in all_dim_fields]

        # ## DECIDE WHICH KIND OF PLOT CAN BE USED ## #

        if (start_doc.get("num_points") == 1) and (stream_name == dim_stream) and omit_single_point_plot:
            return []

        # This is a heuristic approach until we think of how to hint this in a
        # generalizable way.
        if stream_name == dim_stream:
            dim_fields = dim_fields
        else:
            dim_fields = ["time"]  # 'time' once LivePlot can do that

        ndims = len(dim_fields)
        if not 0 < ndims < 3:
            # we need 1 or 2 dims to do anything, do not make empty figures
            return []

        # if self._fig_factory:
        #     fig = self._fig_factory(fig_name)
        # else:
        #     fig = plt.figure(fig_name)

        # if not fig.axes:
        #     if len(columns) < 5:
        #         layout = (len(columns), 1)
        #     else:
        #         nrows = ncols = int(np.ceil(np.sqrt(len(columns))))
        #         while (nrows - 1) * ncols > len(columns):
        #             nrows -= 1
        #         layout = (nrows, ncols)
        #     if ndims == 1:
        #         share_kwargs = {'sharex': True}
        #     elif ndims == 2:
        #         share_kwargs = {'sharex': True, 'sharey': True}
        #     else:
        #         raise NotImplementedError("we now support 3D?!")

        #     fig_size = np.array(layout[::-1]) * 5
        #     fig.set_size_inches(*fig_size)
        #     fig.subplots(*map(int, layout), **share_kwargs)
        #     for ax in fig.axes[len(columns):]:
        #         ax.set_visible(False)

        # axes = fig.axes

        # ## LIVE PLOT AND PEAK ANALYSIS ## #

        if ndims == 1:
            (x_key,) = dim_fields
            key = (stream_name, x_key, (tuple(columns),))
            try:
                lines_instances = self._lines_instances[key]
            except KeyError:
                lines_instances = []
                axes_list = []
                for y_key in columns:
                    dtype = descriptor["data_keys"][y_key]["dtype"]
                    if dtype not in ("number", "integer"):
                        warn("Omitting {} from plot because dtype is {}" "".format(y_key, dtype))
                        continue
                    axes = Axes(x_label=x_key, title=y_key)
                    axes_list.append(axes)
                    lines_kwargs = {}
                    if self.max_runs is not None:
                        lines_kwargs["max_runs"] = self.max_runs
                    lines = Lines(
                        x=x_key,
                        ys=(y_key,),
                        needs_streams=(stream_name,),
                        axes=axes,
                        **lines_kwargs,
                    )
                    lines_instances.append(lines)
                if not axes_list:
                    return
                title = ", ".join((str(lines.ys[0]) for lines in lines_instances)) + f" vs. {x_key}"
                if len(title) > 15:
                    short_title = title[:15] + "..."
                else:
                    short_title = title
                figure = Figure(axes_list, title=title, short_title=short_title)
                self._lines_instances[key] = lines_instances
                self.plot_builders.extend(lines_instances)
                self.figures.append(figure)
            for lines in lines_instances:
                lines.add_run(run, **kwargs)

        elif ndims == 2:
            return []
            # # Decide whether to use LiveGrid or LiveScatter. LiveScatter is the
            # # safer one to use, so it is the fallback..
            # gridding = self._start_descriptor.get('hints', {}).get('gridding')
            # if gridding == 'rectilinear':
            #     self._live_grids[descriptor['uid']] = {}
            #     slow, fast = dim_fields
            #     try:
            #         extents = self._start_descriptor['extents']
            #         shape = self._start_descriptor['shape']
            #     except KeyError:
            #         warn("Need both 'shape' and 'extents' in plan metadata to "
            #                 "create LiveGrid.")
            #     else:
            #         data_range = np.array([float(np.diff(e)) for e in extents])
            #         y_step, x_step = data_range / [max(1, s - 1) for s in shape]
            #         adjusted_extent = [extents[1][0] - x_step / 2,
            #                             extents[1][1] + x_step / 2,
            #                             extents[0][0] - y_step / 2,
            #                             extents[0][1] + y_step / 2]
            #         for I_key, ax in zip(columns, axes):
            #             # MAGIC NUMBERS based on what tacaswell thinks looks OK
            #             data_aspect_ratio = np.abs(data_range[1]/data_range[0])
            #             MAR = 2
            #             if (1/MAR < data_aspect_ratio < MAR):
            #                 aspect = 'equal'
            #                 ax.set_aspect(aspect, adjustable='box')
            #             else:
            #                 aspect = 'auto'
            #                 ax.set_aspect(aspect, adjustable='datalim')

            #             live_grid = LiveGrid(shape, I_key,
            #                                     xlabel=fast, ylabel=slow,
            #                                     extent=adjusted_extent,
            #                                     aspect=aspect,
            #                                     ax=ax)

            #             live_grid('start', self._start_descriptor)
            #             live_grid('descriptor', descriptor)
            #             self._live_grids[descriptor['uid']][I_key] = live_grid
            # else:
            #     self._live_scatters[descriptor['uid']] = {}
            #     x_key, y_key = dim_fields
            #     for I_key, ax in zip(columns, axes):
            #         try:
            #             extents = self._start_descriptor['extents']
            #         except KeyError:
            #             xlim = ylim = None
            #         else:
            #             xlim, ylim = extents
            #         live_scatter = LiveScatter(x_key, y_key, I_key,
            #                                     xlim=xlim, ylim=ylim,
            #                                     # Let clim autoscale.
            #                                     ax=ax)
            #         live_scatter('start', self._start_descriptor)
            #         live_scatter('descriptor', descriptor)
            #         self._live_scatters[descriptor['uid']][I_key] = live_scatter

        else:
            raise NotImplementedError("we do not support 3D+ in BEC yet (and it should have bailed above)")
