from collections import defaultdict, namedtuple


AxesSpec = namedtuple("AxesSpec", ["x_label", "y_label"])
"Describes axes"

LineSpec = namedtuple("LineSpec", ["func", "run", "axes_spec", "args", "kwargs"])
"Describes a line (both data and style)"


def consumer(run):
    def func(run):
        ds = run.primary.read()
        return ds["motor"], ds["det"]

    axes_spec = AxesSpec("motor", "det")

    return [LineSpec(func, run, axes_spec, (), {})]



"""
    omit_single_point_plot = Bool(True, config=True)
    line_class = Type()

    @default('line_class')
    def default_line_class(self):
        # By defining the default value of line_class dynamically here, we
        # avoid importing matplotlib if some non-matplotlib line_class is
        # specfied by configuration.
        from ..artists.mpl.line import Line
        return Line

    def __init__(self, fig_manager, dimensions):
        self.update_config(load_config())
        self.fig_manager = fig_manager
        self.start_doc = None
        self.dimensions = dimensions
        self.dim_streams = set(stream for _, stream in self.dimensions)
        if len(self.dim_streams) > 1:
            raise NotImplementedError

    def __call__(self, name, start_doc):
        self.start_doc = start_doc
        return [], [self.subfactory]

    def subfactory(self, name, descriptor_doc):
        if self.omit_single_point_plot and self.start_doc.get('num_points') == 1:
            return []
        if len(self.dimensions) > 1:
            return []  # This is a job for Grid.
        fields = set(hinted_fields(descriptor_doc))
        # Filter out the fields with a data type or shape that we cannot
        # represent in a line plot.
        for field in list(fields):
            dtype = descriptor_doc['data_keys'][field]['dtype']
            if dtype not in ('number', 'integer'):
                fields.discard(field)
            ndim = len(descriptor_doc['data_keys'][field]['shape'] or [])
            if ndim != 0:
                fields.discard(field)

        callbacks = []
        dim_stream, = self.dim_streams  # TODO Handle multiple dim_streams.
        if descriptor_doc.get('name') == dim_stream:
            dimension, = self.dimensions
            x_keys, stream_name = dimension
            fields -= set(x_keys)
            assert stream_name == dim_stream  # TODO Handle multiple dim_streams.
            for x_key in x_keys:
                figure_label = f'Scalars v {x_key}'
                fig = self.fig_manager.get_figure(
                    ('line', x_key, tuple(fields)), figure_label, len(fields), sharex=True)
                for y_key, ax in zip(fields, fig.axes):

                    log.debug('plot %s against %s', y_key, x_key)

                    ylabel = y_key
                    y_units = descriptor_doc['data_keys'][y_key].get('units')
                    ax.set_ylabel(y_key)
                    if y_units:
                        ylabel += f' [{y_units}]'
                    # Set xlabel only on lowest axes, outside for loop below.

                    def func(event_page, y_key=y_key):
                        y_data = event_page['data'][y_key]
                        if x_key == 'time':
                            t0 = self.start_doc['time']
                            x_data = numpy.asarray(event_page['time']) - t0
                        elif x_key == 'seq_num':
                            x_data = event_page['seq_num']
                        else:
                            x_data = event_page['data'][x_key]
                        return x_data, y_data

                    line = self.line_class(func, ax=ax)
                    callbacks.append(line)

                if fields:
                    # Set the xlabel on the bottom-most axis.
                    if x_key == 'time':
                        xlabel = x_key
                        x_units = 's'
                    elif x_key == 'seq_num':
                        xlabel = 'sequence number'
                        x_units = None
                    else:
                        xlabel = x_key
                        x_units = descriptor_doc['data_keys'][x_key].get('units')
                    if x_units:
                        xlabel += f' [{x_units}]'
                    ax.set_xlabel(x_key)
                    fig.tight_layout()
            # TODO Plot other streams against time.
        for callback in callbacks:
            callback('start', self.start_doc)
            callback('descriptor', descriptor_doc)
        return callbacks
"""
