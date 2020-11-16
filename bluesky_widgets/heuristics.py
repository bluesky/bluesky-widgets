from collections import defaultdict, namedtuple
from warnings import warn


AxesSpec = namedtuple("AxesSpec", ["x_label", "y_label"])
"Describes axes"

LineSpec = namedtuple("LineSpec", ["func", "run", "axes_spec", "args", "kwargs"])
"Describes a line (both data and style)"


def prompt_line_builder(run):
    def func(run):
        ds = run.primary.read()
        return ds["motor"], ds["det"]

    axes_spec = AxesSpec("motor", "det")

    return [LineSpec(func, run, axes_spec, (), {})]


def lines(run):
    start_doc = run.metadata["start"]
    dimensions = start_doc.get("hints", {}).get(
        "dimensions", guess_dimensions(start_doc)
    )
    dim_streams = set(stream for _, stream in dimensions)
    if len(dim_streams) > 1:
        raise NotImplementedError

    omit_single_point_plot = True  # TODO Make this configurable?
    if omit_single_point_plot and start_doc.get("num_points") == 1:
        return []
    if len(dimensions) > 1:
        return []  # This is a job for Grid.

    def new_stream(stream):
        fields = set(hinted_fields(descriptor_doc))
        # Filter out the fields with a data type or shape that we cannot
        # represent in a line plot.
        for field in list(fields):
            dtype = descriptor_doc["data_keys"][field]["dtype"]
            if dtype not in ("number", "integer"):
                fields.discard(field)
            ndim = len(descriptor_doc["data_keys"][field]["shape"] or [])
            if ndim != 0:
                fields.discard(field)

        specs = []
        (dim_stream,) = dim_streams  # TODO Handle multiple dim_streams.
        if descriptor_doc.get("name") == dim_stream:
            (dimension,) = dimensions
            x_keys, stream_name = dimension
            fields -= set(x_keys)
            assert stream_name == dim_stream  # TODO Handle multiple dim_streams.
            for x_key in x_keys:
                figure_label = f"Scalars v {x_key}"
                fig = self.fig_manager.get_figure(
                    ("line", x_key, tuple(fields)),
                    figure_label,
                    len(fields),
                    sharex=True,
                )
                for y_key, ax in zip(fields, fig.axes):

                    log.debug("plot %s against %s", y_key, x_key)

                    ylabel = y_key
                    y_units = descriptor_doc["data_keys"][y_key].get("units")
                    ax.set_ylabel(y_key)
                    if y_units:
                        ylabel += f" [{y_units}]"
                    # Set xlabel only on lowest axes, outside for loop below.

                    def func(event_page, y_key=y_key):
                        y_data = event_page["data"][y_key]
                        if x_key == "time":
                            t0 = self.start_doc["time"]
                            x_data = numpy.asarray(event_page["time"]) - t0
                        elif x_key == "seq_num":
                            x_data = event_page["seq_num"]
                        else:
                            x_data = event_page["data"][x_key]
                        return x_data, y_data

                    line = self.line_class(func, ax=ax)
                    callbacks.append(line)

                if fields:
                    # Set the xlabel on the bottom-most axis.
                    if x_key == "time":
                        xlabel = x_key
                        x_units = "s"
                    elif x_key == "seq_num":
                        xlabel = "sequence number"
                        x_units = None
                    else:
                        xlabel = x_key
                        x_units = descriptor_doc["data_keys"][x_key].get("units")
                    if x_units:
                        xlabel += f" [{x_units}]"
                    ax.set_xlabel(x_key)
                    fig.tight_layout()
            # TODO Plot other streams against time.
        return callbacks

    from warnings import warn

    def guess_dimensions(start_doc):
        """
        Parameters
        ----------
        Prepare a guess about the dimensions (independent variables).
        start_doc : dict
        Returns
        -------
        dimensions : list
            looks like a plan's 'dimensions' hint, but guessed from heuristics
        """
        motors = start_doc.get("motors")
        if motors is not None:
            return [([motor], "primary") for motor in motors]
            # For example, if this was a 2D grid scan, we would have:
            # [(['x'], 'primary'), (['y'], 'primary')]
        else:
            # There is no motor, so we will guess this is a time series.
            return [(["time"], "primary")]

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

    def extract_hints_info(start_doc):
        """
        Parameters
        ----------
        start_doc : dict
        Returns
        -------
        stream_name, dim_fields, all_dim_fields
        """
        plan_hints = start_doc.get("hints", {})

        # Use the guess if there is not hint about dimensions.
        dimensions = plan_hints.get("dimensions")
        if dimensions is None:
            dimensions = guess_dimensions(start_doc)

        # Do all the 'dimensions' belong to the same Event stream? If not, that is
        # too complicated for this implementation, so we ignore the plan's
        # dimensions hint and fall back on guessing.
        if len(set(stream_name for fields, stream_name in dimensions)) != 1:
            dimensions = guess_dimensions(start_doc)
            warn(
                "We are ignoring the dimensions hinted because we cannot "
                "combine streams."
            )

        # for each dimension, choose one field only
        # the plan can supply a list of fields. It's assumed the first
        # of the list is always the one plotted against
        # fields could be just one field, like ['time'] or ['x'], but for an "inner
        # product scan", it could be multiple fields like ['x', 'y'] being scanned
        # over jointly. In that case, we just plot against the first one.
        dim_fields = [first_field for (first_field, *_), stream_name in dimensions]

        # Make distinction between flattened fields and plotted fields.
        # Motivation for this is that when plotting, we find dependent variable
        # by finding elements that are not independent variables
        all_dim_fields = [
            field for fields, stream_name in dimensions for field in fields
        ]  # noqa

        # Above we checked that all the dimensions belonged to the same Event
        # stream, so we can take the stream_name from any item in the list of
        # dimensions, and we'll get the same result. Might as well use the first
        # one.
        _, dim_stream = dimensions[0]  # so dim_stream is like 'primary'
        # TO DO -- Do we want to return all of these? Maybe we should just return
        # 'dimensions' and let the various callback_factories do whatever
        # transformations they need.
        return dim_stream, dim_fields, all_dim_fields
