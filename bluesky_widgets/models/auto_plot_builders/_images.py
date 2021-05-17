from ..plot_builders import Images
from ._base import AutoPlotter


class AutoImages(AutoPlotter):
    """
    Construct figures with line plots automatically.

    The decision of which lines to plot is based on metadata and data shape.

    Examples
    --------

    View with Jupyter.

    >>> model = AutoImages()
    >>> from bluesky_widgets.jupyter.figures import JupyterFigures
    >>> view = JupyterFigures(model.figures)
    >>> model.add_run(run)
    """

    def __init__(self, *, max_runs=None):
        super().__init__()
        # Map (stream_name, field) to instance of Images
        self._field_to_builder = {}
        self._max_runs = max_runs

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

    def handle_new_stream(self, run, stream_name):
        """
        This is used internally and should not be called directly by user code.

        Given a run and stream name, add or update figures with images.

        Parameters
        ----------
        run : BlueskyRun
        stream_name : String
        """
        ds = run[stream_name].to_dask()
        for field in ds:
            if 2 <= ds[field].ndim < 5:
                key = (stream_name, field, run.metadata["start"]["uid"])
                try:
                    images = self._field_to_builder[key]
                except KeyError:
                    images = Images(field=field, needs_streams=(stream_name,))
                    self._field_to_builder[key] = images
                    self.plot_builders.append(images)
                    self.figures.append(images.figure)
                images.add_run(run)
