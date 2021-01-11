from ..plot_builders import Images
from .base import AutoPlotter


class AutoImages(AutoPlotter):
    def __init__(self, *, max_runs=None):
        super().__init__()
        # Map field to instance of Images
        self._field_to_builder = {}
        self._max_runs = max_runs

    @property
    def max_runs(self):
        return self._max_runs

    @max_runs.setter
    def max_runs(self, value):
        if max_runs is not None:
            for lines_instances in self._lines_instances.values():
                for lines in line_instances:
                    line.max_runs = value
        self._max_runs = max_runs

    def handle_new_stream(self, run, stream_name):
        """
        Given a run and stream name, add or update figures with images.

        Parameters
        ----------
        run : BlueskyRun
        stream_name : String
        """
        ds = run[stream_name].to_dask()
        for field in ds:
            if 2 <= ds[field].ndim < 5:
                images = Images(field=field, needs_streams=(stream_name,))
                self.plot_builders.append(images)
                self.figures.append(images.figure)
