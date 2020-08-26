from datetime import datetime, timedelta

import tzlocal

from .queries import TimeRange, InvertedRange
from ...utils.event import EmitterGroup, Event

TIMEZONE = tzlocal.get_localzone().zone


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
        self._time_validator = None
        # Initialize defaults. Some front ends (e.g. Qt) cannot have a null
        # state, so we pick an arbitrary range.
        self.since = datetime.now() - timedelta(days=365)
        self.until = datetime.now() + timedelta(days=365)

    @property
    def time_validator(self):
        return self._time_validator

    @time_validator.setter
    def time_validator(self, validator):
        self._time_validator = validator

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
        if self.time_validator is not None:
            self.time_validator(since=since, until=self.until)
        if isinstance(since, (int, float)):
            since = datetime.fromtimestamp(since)
        if isinstance(since, datetime) and since == self.since:
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
        if self.time_validator is not None:
            self.time_validator(since=self.since, until=until)
        if isinstance(until, (int, float)):
            until = datetime.fromtimestamp(until)
        if isinstance(until, datetime) and until == self.until:
            return
        self._until = until
        self.events.until(date=until)

    def on_since(self, event):
        try:
            since, until = ensure_abs(event.date, self._until)
            tr = TimeRange(since=since, until=until)
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
            since, until = ensure_abs(self._since, event.date)
            tr = TimeRange(since=since, until=until)
        except InvertedRange:
            # Move 'since' as well to create a valid (though empty) interval.
            self.since = event.date
            return
        if tr:
            self._query.update(tr)
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
