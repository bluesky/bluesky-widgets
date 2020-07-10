"""
Vendored a *simplified* version of databroker.queries here.

The "human-friendly time parsing" bits have been removed, because GUI datetime
inputs give us sensible types.
"""
import abc
import collections.abc


class Query(collections.abc.Mapping):
    """
    This represents a MongoDB query.

    MongoDB queries are typically encoded as simple dicts. This object supports
    the dict interface in a read-only fashion. Subclassses add a nice __repr__
    and mutable attributes from which the contents of the dict are derived.
    """
    @abc.abstractproperty
    def query(self):
        ...

    @abc.abstractproperty
    def kwargs(self):
        ...

    def __iter__(self):
        return iter(self.query)

    def __getitem__(self, key):
        return self.query[key]

    def __len__(self):
        return len(self.query)

    def replace(self, **kwargs):
        """
        Make a copy with parameters changed.
        """
        return type(self)(**{**self.kwargs, **kwargs})

    def __repr__(self):
        return (f"{type(self).__name__}("
                f"{', '.join(f'{k}={v}' for k, v in self.kwargs.items())})")


class TimeRange(Query):
    """
    A search query representing a time range.

    Parameters
    ----------
    since, until: dates gives as timestamp, datetime, or human-friendly string, optional

    Examples
    --------
    Any granularity (year, month, date, hour, minute, second) is accepted.

    >>> TimeRange(since='2014')

    >>> TimeRange(until='2019-07')

    >>> TimeRange(since='2014-07-04', until='2020-07-04')

    >>> TimeRange(since='2014-07-04 05:00')

    Create a copy replacing some parameter. This leaves the original unchanged.

    >>> tr = TimeRange(since='2014-07-04 05:00')
    >>> tr.replace(until='2015')
    TimeRange(since='2014-07-04 05:00', until='2015')
    >>> tr
    TimeRange(since='2014-07-04 05:00')

    Access the raw query that this generates.

    >>> TimeRange(since='2014').query
    {'time': {'$gte': 1388552400.0}}
    """
    def __init__(self, since=None, until=None):
        self.since = since
        self.until = until
        if since is not None and until is not None:
            if since > until:
                raise ValueError("since must not be greater than until.")

    @property
    def kwargs(self):
        return {'since': self.since,
                'until': self.until}

    @property
    def query(self):
        query = {'time': {}}
        if self.since is not None:
            query['time']['$gte'] = self.since
        if self.until is not None:
            query['time']['$lt'] = self.until
        if query['time']:
            return query
        else:
            return {}
