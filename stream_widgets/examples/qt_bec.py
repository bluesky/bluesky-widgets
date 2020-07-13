from qtpy.QtWidgets import QWidget, QVBoxLayout

from stream_widgets.qt import Window
from stream_widgets.components.search.search_input import SearchInput
from stream_widgets.components.search.search_results import SearchResults
from stream_widgets.components.search.catalog_controller import CatalogController
from stream_widgets.qt.search_input import QtSearchInput
from stream_widgets.qt.search_results import QtSearchResults

from stream_widgets.examples.utils.generate_msgpack_data import get_catalog


headings = (
    'Unique ID',
    'Transient Scan ID',
    'Plan Name',
    'Start Time',
    'Duration',
    'Exit Status',
)


def extract_results_row_from_run(run):
    """
    Given a BlueskyRun, format a row for the table of search results.
    """
    from datetime import datetime
    metadata = run.describe()['metadata']
    start = metadata['start']
    stop = metadata['stop']
    start_time = datetime.fromtimestamp(start['time'])
    if stop is None:
        str_duration = '-'
    else:
        duration = datetime.fromtimestamp(stop['time']) - start_time
        str_duration = str(duration)
        str_duration = str_duration[:str_duration.index('.')]
    return (
        start['uid'][:8],
        start.get('scan_id', '-'),
        start.get('plan_name', '-'),
        start_time.strftime('%Y-%m-%d %H:%M:%S'),
        str_duration,
        '-' if stop is None else stop['exit_status']
    )


columns = (headings, extract_results_row_from_run)


class ViewerModel:
    """
    Compose various models (search input, search results, ...) into one object.
    """
    def __init__(self, title):
        self.title = title
        self.search_input = SearchInput()
        self.search_results = SearchResults((headings, extract_results_row_from_run))
        catalog = get_catalog()
        self._catalog_controller = CatalogController(
            catalog,
            self.search_input,
            self.search_results
        )
        super().__init__()


class QtViewer(QWidget):
    """
    A Qt-based front-end to ViewerModel

    Take a ViewerModel and wrap each component in a correspdong QWidget, and
    arrange the widgets in a layout.

    This may be embedded in some other application's Main Window.
    """
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewer = model
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtSearchInput(model.search_input))
        layout.addWidget(QtSearchResults(model.search_results))


class Viewer(ViewerModel):
    """
    The user-facing Qt-based Viewer.

    Compose the model with QtViewer and a Qt Main Window, so the user has just
    one object to handle.

    This cannot be embedded in another application's Main Window. Use QtViewer
    to do that.
    """
    def __init__(self, *, show=True, title=""):
        super().__init__(title=title)
        qt_viewer = QtViewer(self)
        self.window = Window(qt_viewer, show=show)

    def show(self):
        """Resize, show, and raise the viewer window."""
        self.window.show()

    def close(self):
        """Close the viewer window."""
        self.window.close()


def main():
    from stream_widgets.qt import gui_qt

    with gui_qt("Example Aplication"):
        Viewer()


if __name__ == "__main__":
    main()
