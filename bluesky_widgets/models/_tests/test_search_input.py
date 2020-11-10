from datetime import datetime, timedelta

import pytest

from ..search import SearchInput, LOCAL_TIMEZONE


def test_instantiation():
    SearchInput()


def test_since_datetime():
    s = SearchInput()

    events = []

    def cb(event):
        events.append(event)

    s.events.since.connect(cb)
    s.since = datetime(2015, 9, 5, tzinfo=LOCAL_TIMEZONE)
    assert s.since == datetime(2015, 9, 5, tzinfo=LOCAL_TIMEZONE)
    assert len(events) == 1
    assert "time" in s.query
    assert "$gte" in s.query["time"]


def test_since_timedelta():
    s = SearchInput()

    events = []

    def cb(event):
        events.append(event)

    s.events.since.connect(cb)
    s.since = timedelta(days=-5)
    assert s.since == timedelta(days=-5)
    assert len(events) == 1
    assert "time" in s.query
    assert "$gte" in s.query["time"]


def test_until_datetime():
    s = SearchInput()

    events = []

    def cb(event):
        events.append(event)

    s.events.until.connect(cb)
    s.until = datetime(2015, 9, 5, tzinfo=LOCAL_TIMEZONE)
    assert s.until == datetime(2015, 9, 5, tzinfo=LOCAL_TIMEZONE)
    assert len(events) == 1
    assert "time" in s.query
    assert "$lt" in s.query["time"]


def test_until_timedelta():
    s = SearchInput()

    events = []

    def cb(event):
        events.append(event)

    s.events.until.connect(cb)
    s.until = timedelta(days=-5)
    assert s.until == timedelta(days=-5)
    assert len(events) == 1
    assert "time" in s.query
    assert "$lt" in s.query["time"]


def test_clearing():
    s = SearchInput()

    s.until = (2015, 9, 5)
    s.until = None
    s.since = None
    assert "time" not in s.query


def test_time_validator():
    s = SearchInput()

    allowed = {timedelta(days=-1), timedelta(days=-7), timedelta(days=-30)}

    def time_validator(since=None, until=None):
        """
        Enforce that since and until are values that a UI can represent.

        This is an example similar to what will be used in the Qt UI.
        """
        now = timedelta()
        if isinstance(since, timedelta):
            if not (until is None or until == now):
                raise ValueError(
                    "This UI cannot express since=timedelta(...) unless until "
                    "is timedelta() or None."
                )
            for item in allowed:
                if since == item:
                    break
            else:
                # No matches
                raise ValueError(
                    "This UI can only express since as a timedelta if it is "
                    f"one of {allowed}. The value {since} is not allowed"
                )

    s.time_validator = time_validator

    s.until = None
    s.since = timedelta(days=-1)
    s.since = timedelta(days=-7)
    s.since = timedelta(days=-30)
    with pytest.raises(ValueError):
        s.since = timedelta(days=-2)
    with pytest.raises(ValueError):
        s.until = datetime(2015, 9, 5, tzinfo=LOCAL_TIMEZONE)
    with pytest.raises(ValueError):
        s.until = timedelta(days=-1)
