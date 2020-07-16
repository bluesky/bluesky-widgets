import logging
import queue

from qtpy import QtCore
from qtpy.QtCore import (
    QAbstractTableModel,
    # QItemSelection,
    # QItemSelectionModel,
    QThread,
    Qt,
)
from qtpy.QtWidgets import QAbstractItemView, QHeaderView, QTableView


logger = logging.getLogger(__name__)
LOADING_PLACEHOLDER = "..."
CHUNK_SIZE = 5  # max rows to fetch at once


class DataLoader(QThread):
    """
    This loads data and notifies QAbstractTableModel when it is ready.

    Each _SearchResultsModel has one of these. It is created and started when
    the _SearchResultsModel is instantiated, and it is terminated when the
    _SearchResultsModel and destroyed.

    Loop:
    - Receive an index of data to load on the queue.
    - Fetch the data (a potentially long, blocking operation).
    - Mutate the cache of loaded data, keyed on index.
    - Notify QAbstractTableModel of the change so that it is refreshes the
      viewer from the data cache.
    """

    def __init__(self, queue, get_data, data, data_changed, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queue = queue
        self._get_data = get_data
        self._data = data
        self._data_changed = data_changed

    def run(self):
        while True:
            index = self._queue.get()
            row, column = index.row(), index.column()
            try:
                item = self._get_data(row, column)
            except Exception:
                logger.exception("Error while loading search results")
                continue
            self._data[index] = item
            # This triggers a targeted re-paint of one cell. It would be
            # probably be more optimal to get data for a whole *row* and then
            # repaint the whole thing, or even a whole of several rows. This
            # requires some measurement. For now, the performance of this
            # implementation is acceptable. Most important, the application
            # does not lock up at all during data loading.
            self._data_changed.emit(index, index, [])


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

        # State related to asynchronously fetching data
        self._data = {}
        self._request_queue = queue.Queue()
        self._data_loader = DataLoader(
            self._request_queue, self.model.get_data, self._data, self.dataChanged
        )
        self._data_loader.start()
        self.destroyed.connect(self._data_loader.terminate)

        # Changes to the model update the GUI.
        self.model.events.begin_reset.connect(self.on_begin_reset)
        self.model.events.end_reset.connect(self.on_end_reset)

    def _fetch_data(self, index):
        """Kick off a request to fetch the data"""
        if index in self._data:
            return self._data[index]
        else:
            self._data[index] = LOADING_PLACEHOLDER
            self._request_queue.put(index)
            return LOADING_PLACEHOLDER

    def on_begin_reset(self, event):
        self.beginResetModel()
        self._current_num_rows = 0
        self._catalog_length = len(self.model.catalog)
        self._data.clear()

    def on_end_reset(self, event):
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
        self.beginInsertRows(
            parent, self._current_num_rows, self._current_num_rows + rows_to_add - 1
        )
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
            return self._fetch_data(index)
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
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignHCenter)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
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
