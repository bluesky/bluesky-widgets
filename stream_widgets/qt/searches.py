import logging

from qtpy.QtCore import QStringListModel
from qtpy.QtWidgets import QComboBox, QPushButton, QTabWidget, QVBoxLayout, QWidget
from .search_input import QtSearchInput
from .search_results import QtSearchResults

logger = logging.getLogger(__name__)


class QtSubcatalogSelector(QComboBox):
    """
    ComboBox for selecting a subcatalog from a catalog-of-catalogs.
    """
    def __init__(self, names, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setModel(QStringListModel(names))
        self.setCurrentIndex(-1)


class QtSearch(QWidget):
    """
    A Qt view for a Search model.
    """
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._model = model

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # A "Back" button
        self._back_button = QPushButton("Back")
        self._back_button.setEnabled(False)
        self.layout.addWidget(self._back_button)
        self._back_button.clicked.connect(model.go_back)

        # Hook up model Events to Qt Slots.
        self._model.events.enter.connect(self.on_enter)
        self._model.events.go_back.connect(self.on_go_back)
        self._model.events.run_search_ready.connect(self.on_run_search_ready)
        self._model.events.run_search_cleared.connect(self.on_run_search_cleared)

        self._selector_widgets = []  # QComboBoxes
        self._run_search_widgets = []  # The SearchInput and SearchOutput widgets

        run_search = model.run_search
        if run_search:
            # The root catalog contains Runs, so immediately display Run Search
            # input and output.
            self._initialize_run_search(
                run_search.search_input,
                run_search.search_results)
            # No need to have a "Back" button in this case
            self._back_button.setVisible(False)
        else:
            # The root catalog is a catalog-of-catalogs, so display a combo
            # box.
            self._initialize_selector(list(model.current_catalog))

    def on_enter(self, event=None):
        "We are entering a subcatalog."
        names = list(event.catalog)
        self._initialize_selector(names)
        self._back_button.setEnabled(True)

    def _initialize_selector(self, names):
        "Create a combobox to select from subcatalogs."
        selector = QtSubcatalogSelector(names)
        self._selector_widgets.append(selector)

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
        "Move up the tree of subcatalogs by one step."
        breadcrumbs = self._model.breadcrumbs
        while len(self._selector_widgets) > len(breadcrumbs) + 1:
            w = self._selector_widgets.pop()
            w.close()
        self._selector_widgets[-1].setEnabled(True)
        if not breadcrumbs:
            # This is the last widget. Disable back button.
            self._back_button.setEnabled(False)

    def on_run_search_ready(self, event):
        "We have a catalog of Runs."
        self._initialize_run_search(event.search_input, event.search_results)
        self._back_button.setEnabled(True)

    def _initialize_run_search(self, search_input, search_results):
        "Create search input and output for a catalog of Runs."
        # Create run search widgets and stash them as state for removal later.
        self._run_search_widgets.extend([
            QtSearchInput(search_input),
            QtSearchResults(search_results)
        ])
        for w in self._run_search_widgets:
            self.layout.addWidget(w)

    def on_run_search_cleared(self, event):
        "Clear search input and output."
        for w in self._run_search_widgets:
            w.close()
        self._run_search_widgets.clear()


class QtSearches(QTabWidget):
    """
    Each tab is a QtSearch.
    """
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
