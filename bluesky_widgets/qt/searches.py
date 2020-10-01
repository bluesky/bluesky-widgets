import logging

from qtpy.QtCore import QStringListModel
from qtpy.QtWidgets import (
    QComboBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QSpacerItem,
    QSizePolicy,
)
from .search_input import QtSearchInput
from .search_results import QtSearchResults
from .threading import create_worker

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
        self.model = model

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        # A "Back" button
        self._back_button = QPushButton("Back")
        self._back_button.setEnabled(False)
        self.layout().addWidget(self._back_button)
        self._back_button.clicked.connect(model.go_back)

        # Hook up model Events to Qt Slots.
        self.model.events.go_back.connect(self.on_go_back)
        self.model.events.run_search_cleared.connect(self.on_run_search_cleared)

        self._selector_widgets = []  # QComboBoxes
        self._run_search_widgets = []  # The SearchInput and SearchOutput widgets

        run_search = model.run_search
        if run_search:
            # The root catalog contains Runs, so immediately display Run Search
            # input and output.
            self._initialize_run_search(
                run_search.search_input, run_search.search_results
            )
            # No need to have a "Back" button in this case
            self._back_button.setVisible(False)
        else:
            # The root catalog is a catalog-of-catalogs, so display a combo
            # box.
            self._initialize_selector(list(model.current_catalog))

    def _initialize_selector(self, names):
        "Create a combobox to select from subcatalogs."
        selector = QtSubcatalogSelector(names)
        self._selector_widgets.append(selector)

        def on_selection(index):
            name = names[index]
            selector.setEnabled(False)

            def on_errored(err):
                logger.exception("Failed to select %r", name, exc_info=err)
                # Reset the combobox selection to an empty value and enable it.
                selector.setCurrentIndex(-1)
                selector.setEnabled(True)

            def on_success(return_value):
                # return_value is None
                if self.model.run_search is None:
                    # We have a Catalog of Catalogs.
                    names = list(self.model.current_catalog)
                    self._initialize_selector(names)
                else:
                    # We have a Catalog of Runs.
                    self._initialize_run_search(
                        self.model.run_search.search_input,
                        self.model.run_search.search_results
                    )
                self._back_button.setEnabled(True)

            create_worker(
                self.model.enter,
                name,
                _connect={"errored": on_errored, "returned": on_success}
            )

        selector.activated.connect(on_selection)
        self.layout().addWidget(selector)
        self.layout().addItem(
            QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Minimum)
        )

    def on_go_back(self, event):
        "Move up the tree of subcatalogs by one step."
        breadcrumbs = self.model.breadcrumbs
        while len(self._selector_widgets) > len(breadcrumbs) + 1:
            widget = self._selector_widgets.pop()
            widget.close()
        self._selector_widgets[-1].setEnabled(True)
        if not breadcrumbs:
            # This is the last widget. Disable back button.
            self._back_button.setEnabled(False)

    def _initialize_run_search(self, search_input, search_results):
        "Create search input and output for a catalog of Runs."
        # Create run search widgets and stash them as state for removal later.
        self._run_search_widgets.extend(
            [QtSearchInput(search_input), QtSearchResults(search_results)]
        )
        for w in self._run_search_widgets:
            self.layout().addWidget(w)

    def on_run_search_cleared(self, event):
        "Clear search input and output."
        for w in self._run_search_widgets:
            w.setParent(None)
        self._run_search_widgets.clear()


class QtSearches(QTabWidget):
    """
    Each tab is a QtSearch.
    """

    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self.currentChanged.connect(self.on_current_changed)

        self.model = model
        self._tabs = {}  # map internal model to tab
        self.model.events.added.connect(self.on_added)
        self.model.events.removed.connect(self.on_removed)
        self.model.events.active.connect(self.on_active_changed)

    # These methods update the view in response to the SearchList model.

    def on_added(self, event):
        tab = QtSearch(event.item)
        self._tabs[event.item] = tab
        self.insertTab(event.index, tab, f"Search {event.item.name}")

    def on_removed(self, event):
        if event.item in self._tabs:
            # A Search has been removed from the SearchList model.
            # Close the associated tab and clean up the associated state.
            widget = self._tabs[event.item]
            index = self.indexOf(widget)
            self.removeTab(index)
            del self._tabs[event.item]
        # Else we are being notified the removal of a tab/model that we
        # initiated in close_tab().

    def on_active_changed(self, event):
        self.setCurrentWidget(self._tabs[event.item])

    # These methods notify the SearchList model to actions in the view.

    def on_current_changed(self, index):
        widget = self.widget(index)
        for model, tab in self._tabs.items():
            if tab is widget:
                widget.model.active = True
                break

    def close_tab(self, index):
        # When closing is initiated from the view, remove the associated Search
        # model from the SearchList model.
        widget = self.widget(index)
        self.removeTab(index)
        del self._tabs[widget.model]
        self.model.remove(widget.model)
