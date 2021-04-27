import collections
import logging

from qtpy import QtCore
from qtpy.QtCore import (
    QAbstractTableModel,
    # QItemSelection,
    # QItemSelectionModel,
    QTimer,
    Qt,
)
from qtpy.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from .threading import create_worker


logger = logging.getLogger(__name__)
LOADING_PLACEHOLDER = "..."
CHUNK_SIZE = 5  # max rows to fetch at once
LOADING_LATENCY = 100  # ms


def _load_data(get_data, indexes):
    "Load a batch of data. This is run in a threadpool."
    for index in indexes:
        row, column = index.row(), index.column()
        try:
            item = get_data(row, column)
        except Exception:
            logger.exception("Error while loading search results")
            continue
        yield index, item


class _SearchResultsModel(QAbstractTableModel):
    """
    Qt model connecting our model to Qt's model--view machinery

    This is implementing two layers of "laziness" to ensure that the app
    remains responsive when large tables are loaded.

    1. Rows are added dynamically using Qt's canFetchMore / fetchMore
    machinery.
    2. Data (which Qt assumes is readily available in memory) is immediately
    filled with LOADING_PLACEHOLDER. Work is kicked off on a thread to later
    update this with the actual data.
    """

    def __init__(self, model, *args, **kwargs):
        self.model = model  # our internal model for the components subpackage
        super().__init__(*args, **kwargs)

        # State related to dynamically adding rows
        self._current_num_rows = 0
        self._catalog_length = len(self.model.catalog)

        # Cache for loaded data
        self._data = {}
        # Queue of indexes of data to be loaded
        self._work_queue = collections.deque()
        # Set of active workers
        self._active_workers = set()

        # Start a timer that will periodically load any data queued up to be loaded.
        self._data_loading_timer = QTimer(self)
        # We run this once to initialize it. The _process_work_queue schedules
        # it to be run again when it completes. This is better than a strictly
        # periodic timer because it ensures that requests do not pile up if
        # _process_work_queue takes longer than LOADING_LATENCY to complete.
        self._data_loading_timer.singleShot(LOADING_LATENCY, self._process_work_queue)

        # Changes to the model update the GUI.
        self.model.events.begin_reset.connect(self.on_begin_reset)
        self.model.events.end_reset.connect(self.on_end_reset)

    def _process_work_queue(self):
        if self._work_queue:
            worker = create_worker(_load_data, self.model.get_data, tuple(self._work_queue))
            self._work_queue.clear()
            # Track this worker in case we need to ignore it and cancel due to
            # model reset.
            self._active_workers.add(worker)
            worker.finished.connect(lambda: self._active_workers.discard(worker))
            worker.yielded.connect(self.on_item_loaded)
            worker.start()
        # Else, no work to do.
        # Schedule the next processing.
        self._data_loading_timer.singleShot(LOADING_LATENCY, self._process_work_queue)

    def on_item_loaded(self, payload):
        # Update state and trigger Qt to run data() to update its internal model.
        index, item = payload
        self._data[index] = item
        self.dataChanged.emit(index, index, [])

    def on_begin_reset(self, event):
        # The model is about to set a new catalog with a (potentially)
        # different length and (potentially) different entries. Reset our
        # state.
        self.beginResetModel()
        self.removeRows(0, self._current_num_rows - 1)
        self._current_num_rows = 0
        for worker in self._active_workers:
            # Cease allowing this worker to mutate _data so that we do not get
            # any stale updates.
            worker.yielded.disconnect(self.on_item_loaded)
            # To avoid doing useless work, try to cancel the worker. We do not
            # rely on this request being effective.
            worker.quit()
        self._active_workers.clear()
        self._work_queue.clear()
        self._data.clear()

    def on_end_reset(self, event):
        # The model has its new catalog at this point. Now we can take its
        # length.
        self._catalog_length = len(self.model.catalog)
        self.endResetModel()

    def canFetchMore(self, parent=None):
        if parent.isValid():
            return False
        return self._current_num_rows < self._catalog_length

    def fetchMore(self, parent=None):
        if parent.isValid():
            return
        remainder = self._catalog_length - self._current_num_rows
        rows_to_add = min(remainder, CHUNK_SIZE)
        if rows_to_add <= 0:
            return
        self.beginInsertRows(parent, self._current_num_rows, self._current_num_rows + rows_to_add - 1)
        self._current_num_rows += rows_to_add
        self.endInsertRows()

    def rowCount(self, parent=None):
        return self._current_num_rows

    def columnCount(self, parent=None):
        return len(self.model.headings)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return super().headerData(section, orientation, role)
        if orientation == Qt.Horizontal and section < self.columnCount():
            return str(self.model.headings[section])
        elif orientation == Qt.Vertical and section < self.rowCount():
            return section

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():  # does > 0 bounds check
            return QtCore.QVariant()
        if index.column() >= self.columnCount() or index.row() >= self.rowCount():
            return QtCore.QVariant()
        if role == QtCore.Qt.DisplayRole:
            if index in self._data:
                return self._data[index]
            else:
                self._data[index] = LOADING_PLACEHOLDER
                self._work_queue.append(index)
                return LOADING_PLACEHOLDER
        else:
            return QtCore.QVariant()


class QtSearchResults(QTableView):
    """
    Table of search results

    Parameters
    ----------
    model: bluesky_widgets.components.search_results.SearchResults
    """

    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model

        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSortingEnabled(False)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setShowGrid(True)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        # Left alignment prevents column name to move to the right when the last section is stretched
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        # self.setAlternatingRowColors(True)
        self._abstract_table_model = _SearchResultsModel(model)
        self.setModel(self._abstract_table_model)

        # Notify model of changes to selection and activation.
        self.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.clicked.connect(self.on_clicked)

        # Update the view to changes in the model.
        self.model.selected_rows.events.added.connect(self.on_row_added)
        self.model.selected_rows.events.removed.connect(self.on_row_removed)

    def on_selection_changed(self, selected, deselected):
        # One would expect we could ask Qt directly for the rows, as opposed to
        # using set() here, but I cannot find such a method.
        for row in set(index.row() for index in deselected.indexes()):
            if row in self.model.selected_rows:
                self.model.selected_rows.remove(row)
        for row in set(index.row() for index in selected.indexes()):
            if row not in self.model.selected_rows:
                self.model.selected_rows.append(row)

    def on_clicked(self, index):
        self.model.active_row = index.row()

    def on_row_added(self, event):
        """Sync changes to model to view.

        This is expected to be rare, is not yet publicly exposed.
        """
        # TODO -- Not sure what is broken here
        # index1 = self._abstract_table_model.index(event.item, 0)
        # index2 = self._abstract_table_model.index(event.item, self._abstract_table_model.columnCount())
        # selection = QItemSelection(index1, index2)
        # self.selectionModel().select(selection, QItemSelectionModel.Select)
        ...

    def on_row_removed(self, event):
        """Sync changes to model to view.

        This is expected to be rare, is not yet publicly exposed.
        """
        # TODO -- Not sure what is broken here
        # index1 = self._abstract_table_model.index(event.item, 0)
        # index2 = self._abstract_table_model.index(event.item, self._abstract_table_model.columnCount())
        # selection = QItemSelection(index1, index2)
        # self.selectionModel().select(selection, QItemSelectionModel.Deselect)
        ...

    def on_activated_by_model(self, event):
        # TODO
        ...
