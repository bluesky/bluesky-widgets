from datetime import datetime, timedelta

import tzlocal

from .queries import TimeRange, InvertedRange, normalize_human_friendly_time
from ...utils.event import EmitterGroup, Event

TIMEZONE = tzlocal.get_localzone().zone


class SearchInput:
    def __init__(self):
        self._since = None
        self._until = None
        self._query = {}
        self.events = EmitterGroup(
            source=self,
            auto_connect=True,
            query=Event,
            since=Event,
            until=Event,
            reload=Event,
        )
        # Initialize defaults. Some front ends (e.g. Qt) cannot have a null
        # state, so we pick an arbitrary range.
        self.since = datetime.now() - timedelta(days=365)
        self.until = datetime.now() + timedelta(days=365)

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

    @property
    def since(self):
        """
        Lower bound on time range
        """
        return self._since

    @since.setter
    def since(self, since):
        since = normalize_human_friendly_time(since, tz=TIMEZONE)
        if since == self.since:
            return
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
        until = normalize_human_friendly_time(until, tz=TIMEZONE)
        if until == self.until:
            return
        self._until = until
        self.events.until(date=until)

    def on_since(self, event):
        try:
            tr = TimeRange(since=event.date, until=self._until)
        except InvertedRange:
            # Move 'until' as well to create a valid (though empty) interval.
            self.until = event.date
            return
        if tr:
            self._query.update(tr)
        else:
            self._query.pop("time", None)
        self.events.query(query=self._query)

    def on_until(self, event):
        try:
            tr = TimeRange(since=self._since, until=event.date)
        except InvertedRange:
            # Move 'since' as well to create a valid (though empty) interval.
            self.since = event.date
            return
        if tr:
            self._query.update(tr)
        else:
            self._query.pop("time", None)
        self.events.query(query=self._query)
