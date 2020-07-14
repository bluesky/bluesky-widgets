from qtpy import QtCore
from qtpy.QtWidgets import QComboBox, QTabWidget, QVBoxLayout, QWidget
from .search_input import QtSearchInput
from .search_results import QtSearchResults


class _QtSubcatalogModel(QtCore.QStringListModel):
    def __init__(self, model, *args, **kwargs):
        self._model = model
        super().__init__(*args, **kwargs)
        self._items = []

        # TODO Be lazy about this, as we already are for SearchResults.
        self._items.extend(list(self._model.catalog))
        print(self._items)

    def rowCount(self, parent=None):
        return len(self._model.catalog)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():  # does > 0 bounds check
            return QtCore.QVariant()
        if index.row() >= self.rowCount():
            return QtCore.QVariant()
        if role == QtCore.Qt.DisplayRole:
            item = self._items[index.row()]
            print('item', item)
            return item
        else:
            return QtCore.QVariant()

    # TODO When selected, poke self.model.down(name).


class QtSubcatalogSelector(QComboBox):
    def __init__(self, catalog, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setModel(_QtSubcatalogModel(catalog))


class QtSearch(QWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._model = model

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self._model.events.catalog.connect(self.on_catalog)
        self.on_catalog()

    def on_catalog(self, event=None):
        if self._model.catalog_has_runs:
            self.layout.addWidget(QtSearchInput(self._model.input))
            self.layout.addWidget(QtSearchResults(self._model._search_results))
        else:
            # TODO
            self.layout.addWidget(QtSubcatalogSelector(self._model))


class QtSearches(QTabWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)

        self._model = model
        self._model.events.added.connect(self.on_added)
        self._model.events.removed.connect(self.on_removed)

    def on_added(self, event):
        self.insertTab(event.index, QtSearch(event.item), "Search __")

    def on_removed(self, event):
        self.close_tab(event.index)

    def close_tab(self, index):
        self.removeTab(index)
