from ...utils.event import EmitterGroup, Event


class SearchResults:
    """
    Parameters
    ----------
    columns: tuple
        Expected to have two elements. First is a list of columns names. Second
        is a function that gives the values for one result row.
        Expected signature::
            f(BlueskyRun) -> tuple[str]
    """
    def __init__(self, columns):
        self._catalog = {}
        self._row_cache = {}
        self.columns = columns
        self.events = EmitterGroup(
            source=self,
            auto_connect=True,
            reset=Event
        )

    @property
    def headings(self):
        return self._headings

    @property
    def columns(self):
        return self._columns

    @columns.setter
    def columns(self, columns):
        self._row_cache.clear()
        self._columns = columns
        self._headings, self._row_factory = columns

    def set_results(self, catalog):
        self._row_cache.clear()
        self._catalog = catalog
        self._iterator = iter(catalog)
        self._uids = []
        self.events.reset()

    def get_length(self):
        return len(self._catalog)

    def get_data(self, row, column):
        """
        Get data for one item of the display table.
        """
        assert row < len(self._catalog)
        cache_length = len(self._uids)
        if row >= cache_length:
            for _ in range(row - cache_length + 1):
                self._uids.append(next(self._iterator))
        uid = self._uids[row]
        # To save on function calls, format one whole row in one step and cache
        # the result.
        try:
            row_content = self._row_cache[uid]
        except KeyError:
            run = self._catalog[uid]
            row_content = self._row_factory(run)
            self._row_cache[uid] = row_content
        item_content = row_content[column]  # content for one cell of the grid
        return item_content
