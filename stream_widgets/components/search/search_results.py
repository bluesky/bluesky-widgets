from ...utils.event import EmitterGroup, Event
from ...utils.list import ListModel


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
        self._selected_rows = ListModel()
        self.columns = columns
        self.events = EmitterGroup(source=self, auto_connect=True, reset=Event)

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

    @property
    def catalog(self):
        "Catalog of current results"
        return self._catalog

    @catalog.setter
    def catalog(self, catalog):
        self._row_cache.clear()
        self._catalog = catalog
        self._iterator = iter(catalog)
        self._uids = []
        self._selected_rows.clear()
        self.events.reset()

    def get_data(self, row, column):
        """
        Get data for one item of the display table.
        """
        uid = self.get_uid_by_row(row)
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

    def get_uid_by_row(self, row):
        if row > len(self._catalog):
            raise ValueError(
                f"Cannot get row {row}. Catalog has {len(self._catalog)} rows."
            )
        cache_length = len(self._uids)
        if row >= cache_length:
            for _ in range(row - cache_length + 1):
                self._uids.append(next(self._iterator))
        return self._uids[row]

    @property
    def selected_rows(self):
        return self._selected_rows

    @property
    def selected_uids(self):
        return [self.get_uid_by_row(row) for row in self._selected_rows]

    @property
    def selection_as_catalog(self):
        "A Catalog containing the selected rows"
        return self.catalog.search({"uid": {"$in": self.selected_uids}})
