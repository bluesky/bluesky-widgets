from .search_input import SearchInput
from .search_results import SearchResults
from ...utils.event import EmitterGroup, Event
from ...utils.list import ListModel


class Search:
    def __init__(self, root_catalog, *, columns):
        self.input = SearchInput()
        self._search_results = SearchResults(columns)
        self._breadcrumbs = []
        self._root_catalog = self._catalog = root_catalog
        self._results = None
        self.input.events.query.connect(self._on_query)
        # Initialize the results with the initial state of SearchInput.
        self.input.events.query(query=self.input.query)
        self.events = EmitterGroup(
            source=self,
            auto_connect=True,
            catalog=Event
        )

    @property
    def catalog(self):
        return self._catalog

    def down(self, name):
        old = self._catalog
        new = self._catalog[name]

        # Touch an attribute that will trigger a connection attempt. (It's here
        # that an error would be raised if, say, a database is unreachable.)
        new.metadata

        # If we get this far, it worked.
        self._catalog = new
        self._breadcrumbs.append(old)
        self.events.catalog(self._catalog)

    def up(self):
        self._catalog = self._breadcrumbs.pop()
        self.events.catalog(self._catalog)

    @staticmethod
    def _has_runs(catalog):
        "Is this a catalog BlueskyRuns, or a Catalog of Catalogs?"
        # HACK!
        from databroker.v2 import Broker
        return isinstance(catalog, Broker)

    @property
    def catalog_has_runs(self):
        return self._has_runs(self._catalog)

    @property
    def results(self):
        # For convenience in console, having in mind usage like
        # >>> viewer.active_search.results
        # to get the catalog.
        return self._search_results.catalog

    def _on_query(self, event):
        results = self._catalog.search(event.query)
        self._search_results.catalog = results


class SearchList(ListModel):
    ...
