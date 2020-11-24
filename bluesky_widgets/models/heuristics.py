"""
This module and all the interfaces in it are *highly* provisional likely to be
drastically re-thought in the near future.

This is roughly adapted from bluesky.callbacks.best_effort.
"""
from warnings import warn


def infer_lines_to_plot(run, stream):
    """
    Given a run and stream, suggest what to plot.

    Parameters
    ----------
    run : BlueskyRun
    stream : BlueskyEventStream

    Returns
    -------
    suggestions : List[Tuple[String], String]
        Structured as [((x, y), stream_name), ...]

    Examples
    --------

    A "suggestion" looks like this.

    >>> infer_lines(run1)
    [(("motor", "det"), "primary")]

    Sometimes there are no suggestions.

    >>> infer_lines(run1)
    []
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
        warn(
            "We are ignoring the dimensions hinted because we cannot "
            "combine streams."
        )

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
    descriptor = stream._descriptors[0]  # HACK!
    stream_name = descriptor.get("name", "primary")  # fall back for old descriptors

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

    if (
        (start_doc.get("num_points") == 1)
        and (stream_name == dim_stream)
        and omit_single_point_plot
    ):
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
        return

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
        stuff = []
        for y_key in columns:
            dtype = descriptor["data_keys"][y_key]["dtype"]
            if dtype not in ("number", "integer"):
                warn(
                    "Omitting {} from plot because dtype is {}" "".format(y_key, dtype)
                )
                continue
            stuff.append(((x_key, y_key), stream_name))
        return stuff

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
        raise NotImplementedError(
            "we do not support 3D+ in BEC yet " "(and it should have bailed above)"
        )


def hinted_fields(descriptor):
    # Figure out which columns to put in the table.
    obj_names = list(descriptor["object_keys"])
    # We will see if these objects hint at whether
    # a subset of their data keys ('fields') are interesting. If they
    # did, we'll use those. If these didn't, we know that the RunEngine
    # *always* records their complete list of fields, so we can use
    # them all unselectively.
    columns = []
    for obj_name in obj_names:
        try:
            fields = descriptor.get("hints", {}).get(obj_name, {})["fields"]
        except KeyError:
            fields = descriptor["object_keys"][obj_name]
        columns.extend(fields)
    return columns
