import logging

from qtpy.QtCore import QStringListModel
from qtpy.QtWidgets import QComboBox, QTabWidget, QVBoxLayout, QWidget
from .search_input import QtSearchInput
from .search_results import QtSearchResults

logger = logging.getLogger(__name__)


class QtSubcatalogSelector(QComboBox):
    def __init__(self, names, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setModel(QStringListModel(names))


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
            names = list(self._model.catalog)
            selector = QtSubcatalogSelector(names)

            def on_selection(index):
                name = names[index]
                try:
                    self._model.down(name)
                except Exception:
                    logger.exception("Failed to select %r", name)
                    self.setCurrentIndex(-1)
                else:
                    selector.setEnabled(False)

            selector.activated.connect(on_selection)
            self.layout.addWidget(selector)


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
