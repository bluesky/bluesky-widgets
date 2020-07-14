from .search_input import SearchInput
from .search_results import SearchResults
from ...utils.event import EmitterGroup, Event
from ...utils.list import ListModel


class RunSearch:
    """
    Model of search input and search results for a search for Runs in a catalog of runs.
    """
    def __init__(self, catalog, columns):
        self.catalog = catalog
        self.search_input = SearchInput()
        self.search_results = SearchResults(columns)
        self.search_input.events.query.connect(self._on_query)
        # Initialize the results with the initial state of SearchInput.
        self.search_input.events.query(query=self.search_input.query)

    def _on_query(self, event):
        results = self.catalog.search(event.query)
        self.search_results.catalog = results

    def destroy(self, name):
        self.events.destroy()


class Search:
    """
    Model for digging into potentially nested catalogs and ending at a catalog of runs.
    """
    def __init__(self, root_catalog, *, columns):
        self._subcatalogs = []
        self._root_catalog = root_catalog
        self._columns = columns
        self._search = None
        self.events = EmitterGroup(
            source=self,
            auto_connect=True,
            enter=Event,
            go_back=Event,
            run_search_ready=Event,
            run_search_cleared=Event,
        )

        if self._has_runs(root_catalog):
            self._search = RunSearch(root_catalog, columns)
            self.events.run_search_ready(
                search_input=self._search.search_input,
                search_results=self._search.search_results
            )

    @property
    def run_search(self):
        return self._search

    @property
    def current_catalog(self):
        if self._subcatalogs:
            return self._subcatalogs[-1]
        else:
            return self._root_catalog

    @property
    def input(self):
        # a convenience accessor
        if self._search is not None:
            return self._search.search_input

    @property
    def results(self):
        # For convenience in console, having in mind usage like
        # >>> viewer.active_search.results
        # to get the catalog.
        return self._search.search_results.catalog

    def enter(self, name):
        if self._search is not None:
            raise RuntimeError("Already all the way into a Catalog of Runs")
        if self._subcatalogs:
            old = self._subcatalogs[-1]
        else:
            old = self._root_catalog
        new = old[name]

        # Touch an attribute that will trigger a connection attempt. (It's here
        # that an error would be raised if, say, a database is unreachable.)
        new.metadata

        # If we get this far, it worked.
        if not self._has_runs(new):
            # Step through another subcatalog.
            self._subcatalogs.append(new)
            self.events.enter(catalog=new)
        else:
            self._search = RunSearch(self._root_catalog, self._columns)
            self.events.run_search_ready(
                search_input=self._search.search_input,
                search_results=self._search.search_results
            )

    def go_back(self):
        if self._search is not None:
            self.run_search_cleared()
            self._search = None
        else:
            self._subcatalogs.pop()
            self.events.go_back()

    @staticmethod
    def _has_runs(catalog):
        "Is this a catalog BlueskyRuns, or a Catalog of Catalogs?"
        # HACK!
        from databroker.v2 import Broker
        return isinstance(catalog, Broker)


class SearchList(ListModel):
    """
    Model for a list of Search models
    """
    ...
