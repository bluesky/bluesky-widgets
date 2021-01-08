from ..plot_builders import Images
from .base import AutoPlotter


class AutoImages(AutoPlotter):
    def handle_new_stream(self, run, stream_name):
        """
        Given a run and stream name, add or update figures with images.

        Parameters
        ----------
        run : BlueskyRun
        stream_name : String
        """
        suggestions = []
        ds = run[stream_name].to_dask()
        for field in ds:
            if 2 <= ds[field].ndim < 5:
                images = Images(field=field, needs_streams=(stream_name,))
                self.plot_builders.append(images)
                self.figures.append(images.figure)
