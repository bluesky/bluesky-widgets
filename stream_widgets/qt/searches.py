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
        self.setCurrentIndex(-1)


class QtSearch(QWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._model = model

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self._model.events.enter.connect(self.on_enter)
        self._model.events.go_back.connect(self.on_go_back)
        self._model.events.run_search_ready.connect(self.on_run_search_ready)
        self._model.events.run_search_cleared.connect(self.on_run_search_cleared)
        self._run_search_widgets = []

        # TODO There must be a clearly way to initialize.
        run_search = model.run_search
        if run_search:
            self._initialize_run_search(
                run_search.search_input,
                run_search.search_results)
        else:
            self._initialize_selector(list(model.current_catalog))

    def on_enter(self, event=None):
        names = list(event.catalog)
        print(types(names), names)
        self._initialize_run_search(names)

    def _initialize_selector(self, names):
        selector = QtSubcatalogSelector(names)

        def on_selection(index):
            name = names[index]
            try:
                self._model.enter(name)
            except Exception:
                logger.exception("Failed to select %r", name)
                selector.setCurrentIndex(-1)
            else:
                selector.setEnabled(False)

        selector.activated.connect(on_selection)
        self.layout.addWidget(selector)

    def on_go_back(self, event):
        ...

    def on_run_search_ready(self, event):
        self._initialize_run_search(event.search_input, event.search_results)

    def _initialize_run_search(self, search_input, search_results):
        # Create run search widgets and stash them as state for removal later.
        self._run_search_widgets = [
            QtSearchInput(search_input),
            QtSearchResults(search_results)
        ]
        for w in self._run_search_widgets:
            self.layout.addWidget(w)

    def on_run_search_cleared(self, event):
        for w in self._run_search_widgets:
            w.close()
        self._run_search_widgets.clear()


class QtSearches(QTabWidget):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)

        self._model = model
        self._model.events.added.connect(self.on_added)
        self._model.events.removed.connect(self.on_removed)

    def on_added(self, event):
        self.insertTab(event.index, QtSearch(event.item), f"Search {event.item.name}")

    def on_removed(self, event):
        self.close_tab(event.index)

    def close_tab(self, index):
        self.removeTab(index)
