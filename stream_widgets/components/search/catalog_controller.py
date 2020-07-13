class CatalogController:
    """
    Connect Catalog to SearchInput and SearchResults.
    """
    def __init__(self, catalog, search_input, search_results):
        self._catalog = catalog
        self.search_input = search_input
        self.search_results = search_results
        self.search_input.events.query.connect(self._on_query)

    def _on_query(self, event):
        results = self._catalog.search(event.query)
        self.search_results.set_results(results)
