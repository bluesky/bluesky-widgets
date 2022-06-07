from datetime import datetime, timedelta
import itertools

import dateutil.tz
from databroker.queries import TimeRange, PartialUID, ScanID
from tiled.queries import FullText

from ..utils.list import EventedList
from ..utils.event import EmitterGroup, Event
from ..utils.dict_view import UpdateOnlyDict

LOCAL_TIMEZONE = dateutil.tz.tzlocal()
_epoch = datetime(1970, 1, 1, 0, 0, tzinfo=LOCAL_TIMEZONE)


class InvertedRange(ValueError):
    ...


# The following are vendored from databroker.utils.

# human friendly timestamp formats we'll parse
_TS_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",  # these 2 are not as originally doc'd,
    "%Y-%m-%d %H",  # but match previous pandas behavior
    "%Y-%m-%d",
    "%Y-%m",
    "%Y",
]

# build a tab indented, '-' bulleted list of supported formats
# to append to the parsing function docstring below
_doc_ts_formats = "\n".join("\t- {}".format(_) for _ in _TS_FORMATS)


def normalize_human_friendly_time(val, tz):
    """Given one of :
    - string (in one of the formats below)
    - datetime (eg. datetime.now()), with or without tzinfo)
    - timestamp (eg. time.time())
    return a timestamp (seconds since jan 1 1970 UTC).

    Non string/datetime values are returned unaltered.
    Leading/trailing whitespace is stripped.
    Supported formats:
    {}
    """
    # {} is placeholder for formats; filled in after def...

    import pytz

    zone = pytz.timezone(tz)  # tz as datetime.tzinfo object
    epoch = pytz.UTC.localize(datetime(1970, 1, 1))
    check = True

    if isinstance(val, str):
        # unix 'date' cmd format '%a %b %d %H:%M:%S %Z %Y' works but
        # doesn't get TZ?

        # Could cleanup input a bit? remove leading/trailing [ :,-]?
        # Yes, leading/trailing whitespace to match pandas behavior...
        # Actually, pandas doesn't ignore trailing space, it assumes
        # the *current* month/day if they're missing and there's
        # trailing space, or the month is a single, non zero-padded digit.?!
        val = val.strip()

        for fmt in _TS_FORMATS:
            try:
                ts = datetime.strptime(val, fmt)
                break
            except ValueError:
                pass

        try:
            if isinstance(ts, datetime):
                val = ts
                check = False
            else:
                # what else could the type be here?
                raise TypeError("expected datetime," " got {:r}".format(ts))

        except NameError:
            raise ValueError("failed to parse time: " + repr(val))

    if check and not isinstance(val, datetime):
        return val

    if val.tzinfo is None:
        # is_dst=None raises NonExistent and Ambiguous TimeErrors
        # when appropriate, same as pandas
        val = zone.localize(val, is_dst=None)

    return (val - epoch).total_seconds()


# fill in the placeholder we left in the previous docstring
normalize_human_friendly_time.__doc__ = normalize_human_friendly_time.__doc__.format(_doc_ts_formats)


def secs_since_epoch(datetime):
    return (datetime - _epoch) / timedelta(seconds=1)


def ensure_abs(*abs_or_rel_times):
    """
    If datetime, pass through. If timedelta, interpret as relative to now.
    """
    now = datetime.now()
    results = []
    for item in abs_or_rel_times:
        if isinstance(item, timedelta):
            results.append(now + item)
        else:
            results.append(item)
    return results


class SearchInput:
    def __init__(self, *, fields=None, text_search_supported=False):
        self._since = None
        self._until = None
        self._fields = fields or []
        self._field_search = UpdateOnlyDict(dict.fromkeys(self._fields))
        self._text = None
        self._query = {"fields": {}}
        self.events = EmitterGroup(
            source=self,
            auto_connect=True,
            query=Event,
            since=Event,
            until=Event,
            reload=Event,
            text=Event,
            field_search_updated=Event,
        )
        self._field_search.events.updated.connect(
            lambda event: self.events.field_search_updated(update=event.update)
        )
        self._time_validator = None
        self._text_search_supported = text_search_supported

    @property
    def time_validator(self):
        return self._time_validator

    @time_validator.setter
    def time_validator(self, validator):
        self._time_validator = validator

    @property
    def fields(self):
        return self._fields

    @property
    def text_search_supported(self):
        return self._text_search_supported

    def __repr__(self):
        return f"<SearchInput {self._query!r}>"

    @property
    def query(self):
        """
        MongoDB query
        """
        return self._query

    @query.setter
    def query(self, query):
        if query == self.query:
            return
        self._query = query
        self.events.query(query=query)

    @property
    def since(self):
        """
        Lower bound on time range
        """
        return self._since

    @since.setter
    def since(self, since):
        if self.time_validator is not None:
            self.time_validator(since=since, until=self.until)
        if isinstance(since, (int, float)):
            since = datetime.fromtimestamp(since)
        if isinstance(since, datetime):
            if since == self.since:
                return
            if since.tzinfo is None:
                since = since.replace(tzinfo=LOCAL_TIMEZONE)
        self._since = since
        self.events.since(date=since)

    @property
    def until(self):
        """
        Upper bound on time range
        """
        return self._until

    @until.setter
    def until(self, until):
        if self.time_validator is not None:
            self.time_validator(since=self.since, until=until)
        if isinstance(until, (int, float)):
            until = datetime.fromtimestamp(until)
        if isinstance(until, datetime):
            if until == self.until:
                return
            if until.tzinfo is None:
                until = until.replace(tzinfo=LOCAL_TIMEZONE)
        self._until = until
        self.events.until(date=until)

    @property
    def field_search(self):
        return self._field_search

    @property
    def text(self):
        """
        Text search
        """
        return self._text

    @text.setter
    def text(self, text):
        if text and not self.text_search_supported:
            raise RuntimeError("This catalog does not support text search.")
        self._text = text
        self.events.text(text=text)

    def on_field_search_updated(self, event):
        for field, text in event.update.items():
            if not text:
                self._query["fields"].pop(field, None)
            else:
                self._query["fields"][fields] = text
        self.events.query(query=self._query)

    def on_text(self, event):
        if not event.text:
            self._query.pop("text", None)
        else:
            self._query["text"] = FullText(event.text)
        self.events.query(query=self._query)

    def on_since(self, event):
        try:
            since, until = ensure_abs(event.date, self._until)
            tr = TimeRange(since=since, until=until)
        except InvertedRange:
            # Move 'until' as well to create a valid (though empty) interval.
            self.until = event.date
            return
        if tr:
            self._query["time"] = tr
        else:
            self._query.pop("time", None)
        self.events.query(query=self._query)

    def on_until(self, event):
        try:
            since, until = ensure_abs(self._since, event.date)
            tr = TimeRange(since=since, until=until)
        except InvertedRange:
            # Move 'since' as well to create a valid (though empty) interval.
            self.since = event.date
            return
        if tr:
            self._query["time"] = tr
        else:
            self._query.pop("time", None)
        self.events.query(query=self._query)

    def request_reload(self):
        # If time range was given in relative terms, re-evaluate them relative
        # to the current time.
        changed = False
        if isinstance(self._since, timedelta):
            self.since = self._since
            changed = True
        if isinstance(self._until, timedelta):
            self.until = self._until
            changed = True
        # If the times were re-evaluated, the query Event will have been
        # emitted, so it would be redundant to reload.
        if not changed:
            self.events.reload()


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
        self._selected_rows = EventedList()
        self._active_row = None
        self.columns = columns
        self.events = EmitterGroup(
            source=self,
            auto_connect=True,
            active_row=Event,
            begin_reset=Event,
            end_reset=Event,
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

    @property
    def catalog(self):
        "Catalog of current results"
        return self._catalog

    @catalog.setter
    def catalog(self, catalog):
        self.events.begin_reset()
        self._row_cache.clear()
        self._catalog = catalog
        self._iterator = iter(catalog)
        self._uids = []
        self._selected_rows.clear()
        self.events.end_reset()

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
            raise ValueError(f"Cannot get row {row}. Catalog has {len(self._catalog)} rows.")
        cache_length = len(self._uids)
        if row >= cache_length:
            for _ in range(row - cache_length + 1):
                self._uids.append(next(self._iterator))
        return self._uids[row]

    @property
    def active_row(self):
        return self._active_row

    @active_row.setter
    def active_row(self, active_row):
        if active_row != self.active_row:
            self._active_row = active_row
        self.events.active_row(item=active_row)

    @property
    def active_uid(self):
        if self.active_row is not None:
            return self.get_uid_by_row(self.active_row)

    @property
    def active_run(self):
        if self.active_uid is not None:
            return self.catalog[self.active_uid]

    @property
    def selected_rows(self):
        return self._selected_rows

    @property
    def selected_uids(self):
        return [self.get_uid_by_row(row) for row in self._selected_rows]

    @property
    def selection_as_catalog(self):
        "A Catalog containing the selected rows"
        return self.catalog.search(PartialUID(*self.selected_uids))


class RunSearch:
    """
    Model of search input and search results for a search for Runs in a catalog of runs.
    """

    def __init__(self, catalog, columns):
        self.catalog = catalog
        # TODO Choose a gentler way to do this check.
        # The issue here is that only real MongoDB supports $text queries, not
        # the mongoquery library used by JSONL and msgpack databroker drivers
        # or any other "mock" in-memory MongoDB imitators that we know of.
        try:
            catalog.search(FullText(""))
        except NotImplementedError:
            text_search_supported = False
        else:
            text_search_supported = True
        self.search_input = SearchInput(text_search_supported=text_search_supported)
        self.search_results = SearchResults(columns)
        self.search_input.events.query.connect(self._on_query)
        self.search_input.events.reload.connect(self._on_reload)
        # Initialize the results with the initial state of SearchInput.
        self.search_input.events.query(query=self.search_input.query)

    def _on_reload(self, event):
        self.search_results.events.begin_reset()
        self.search_results.catalog.reload()
        self.search_results.events.end_reset()

    def _on_query(self, event):
        results = self.catalog
        text = event.query.get("text")
        if text:
            results = results.search(text)
        time = event.query.get("time")
        if time:
            results = results.search(time)
        for q in event.query.get("fields", []):
            results = results.search(q)
        self.search_results.catalog = results


class Search:
    """
    Model for digging into potentially nested catalogs and ending at a catalog of runs.
    """

    _name_counter = itertools.count(1)

    def __init__(self, root_catalog, *, name=None, columns):
        if name is None:
            name = self.get_default_name()
        self._name = name
        self._subcatalogs = []
        self._root_catalog = root_catalog
        self._columns = columns
        self._search = None
        self._active = False
        self.events = EmitterGroup(
            source=self,
            auto_connect=True,
            enter=Event,
            go_back=Event,
            run_search_ready=Event,
            run_search_cleared=Event,
            active=Event,
            inactive=Event,
            active_run=Event,
        )

        if self._has_runs(root_catalog):
            self._search = RunSearch(root_catalog, columns)
            self._search.search_results.events.active_row.connect(self._on_active_row)
            self.events.run_search_ready(
                search_input=self._search.search_input,
                search_results=self._search.search_results,
            )

    @classmethod
    def get_default_name(cls):
        return next(cls._name_counter)

    @property
    def name(self):
        return self._name

    @property
    def run_search(self):
        return self._search

    @property
    def root_catalog(self):
        return self._root_catalog

    @property
    def current_catalog(self):
        if self._subcatalogs:
            return self._subcatalogs[-1]
        else:
            return self._root_catalog

    @property
    def breadcrumbs(self):
        "Names of subcatalogs tranversed"
        return [catalog.name for catalog in self._subcatalogs]

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
        if self._search is not None:
            return self._search.search_results.catalog

    @property
    def selected_uids(self):
        if self._search is not None:
            return self._search.search_results.selected_uids

    @property
    def selection_as_catalog(self):
        if self._search is not None:
            return self._search.search_results.selection_as_catalog

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
        self._subcatalogs.append(new)
        if not self._has_runs(new):
            # Step through another subcatalog.
            self.events.enter(catalog=new)
        else:
            self._search = RunSearch(new, self._columns)
            self._search.search_results.events.active_row.connect(self._on_active_row)
            self.events.run_search_ready(
                search_input=self._search.search_input,
                search_results=self._search.search_results,
            )

    def go_back(self):
        if self.root_catalog is self.current_catalog:
            raise RuntimeError("We are the root catalog.")
        if self._search is not None:
            self._search.search_results.events.active_row.disconnect(self._on_active_row)
            self._search = None
            self.events.run_search_cleared()
        self._subcatalogs.pop()
        self.events.go_back()

    def _on_active_row(self, event):
        self.events.active_run(uid=self.active_uid, run=self.active_run)

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, active):
        if active == self.active:
            return
        self._active = active
        if active:
            self.events.active()
        else:
            self.events.inactive()

    @property
    def active_uid(self):
        if self._search is not None:
            return self._search.search_results.active_uid

    @property
    def active_run(self):
        if self._search is not None:
            return self._search.search_results.active_run

    @staticmethod
    def _has_runs(catalog):
        "Is this a catalog BlueskyRuns, or a Catalog of Catalogs?"
        # HACK!
        from databroker.v2 import Broker

        return isinstance(catalog, Broker)


class SearchList(EventedList):
    """
    Model for a list of Search models
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events.add(active=Event)
        self.events.added.connect(self._connect_enforce_mutually_exclusive_activation)
        self.events.removed.connect(self._disconnect_enforce_mutually_exclusive_activation)

    # Ensure that whenever an item in this list become "active" all others are
    # not active.

    def _connect_enforce_mutually_exclusive_activation(self, event):
        event.item.events.active.connect(self._enforce_mutually_exclusive_activation)

    def _disconnect_enforce_mutually_exclusive_activation(self, event):
        event.item.events.active.disconnect(self._enforce_mutually_exclusive_activation)

    def _enforce_mutually_exclusive_activation(self, event):
        for item in self:
            if item is not event.source:
                item.active = False
        self.events.active(item=event.source)

    @property
    def active(self):
        "The active item in the list, if any"
        for item in self:
            if item.active:
                return item
