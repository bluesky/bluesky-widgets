from qtpy import QtCore
from qtpy.QtCore import QAbstractTableModel, Qt
from qtpy.QtWidgets import QAbstractItemView, QHeaderView, QTableView


class _SearchResultsModel(QAbstractTableModel):
    """
    Qt model connecting our model to Qt's model--view machinery
    """
    def __init__(self, model, *args, **kwargs):
        self.model = model  # our internal model for the components subpackage
        super().__init__(*args, **kwargs)

        # Changes to the model update the GUI.
        self.model.events.reset.connect(self.on_entries_changed)

    def on_entries_changed(self, event):
        self.beginResetModel()
        self.endResetModel()

    def rowCount(self, parent=None):
        return self.model.get_length()

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
            return self.model.get_data(index.row(), index.column())
        else:
            return QtCore.QVariant()


class QtSearchResults(QTableView):
    """
    Table of search results

    Parameters
    ----------
    model: stream_widgets.components.search_results.SearchResults
    """
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSortingEnabled(False)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignHCenter)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setModel(_SearchResultsModel(model))
