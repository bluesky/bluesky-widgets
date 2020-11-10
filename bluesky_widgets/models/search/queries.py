"""
Vendored from databroker.queries
"""
import abc
import collections.abc
from datetime import datetime


class InvertedRange(ValueError):
    ...


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
        return (
            f"{type(self).__name__}("
            f"{', '.join(f'{k}={v}' for k, v in self.kwargs.items())})"
        )


class TimeRange(Query):
    """
    A search query representing a time range.

    Parameters
    ----------
    since, until: dates gives as timestamp, datetime, or human-friendly string, optional
    timezone : string
        As in, 'US/Eastern'. If None is given, tzlocal is used.

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

    def __init__(self, since=None, until=None, timezone=None):
        if timezone is None:
            import tzlocal

            timezone = tzlocal.get_localzone().zone
        self.timezone = timezone
        if since is None:
            self._since_normalized = None
        else:
            self._since_normalized = normalize_human_friendly_time(
                since, tz=self.timezone
            )
        self._since_raw = since
        if until is None:
            self._until_normalized = None
        else:
            self._until_normalized = normalize_human_friendly_time(
                until, tz=self.timezone
            )
        self._until_raw = until
        if since is not None and until is not None:
            if self._since_normalized > self._until_normalized:
                raise InvertedRange("since must not be greater than until.")

    @property
    def kwargs(self):
        return {
            "since": self._since_raw,
            "until": self._until_raw,
            "timezone": self.timezone,
        }

    @property
    def query(self):
        query = {"time": {}}
        if self._since_normalized is not None:
            query["time"]["$gte"] = self._since_normalized
        if self._until_normalized is not None:
            query["time"]["$lt"] = self._until_normalized
        if query["time"]:
            return query
        else:
            return {}


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
normalize_human_friendly_time.__doc__ = normalize_human_friendly_time.__doc__.format(
    _doc_ts_formats
)
