from ..search_input import SearchInput


def test_instantiation():
    SearchInput()


def test_since():
    s = SearchInput()

    events = []

    def cb(event):
        events.append(event)

    s.events.since.connect(cb)
    s.since = 5
    assert s.since == 5
    assert len(events) == 1
    assert "time" in s.query
    assert "$gte" in s.query["time"]


def test_until():
    s = SearchInput()

    events = []

    def cb(event):
        events.append(event)

    s.events.until.connect(cb)
    s.until = 5
    assert s.until == 5
    assert len(events) == 1
    assert "time" in s.query
    assert "$lt" in s.query["time"]


def test_clearing():
    s = SearchInput()

    s.until = 5
    s.until = None
    s.since = None
    assert "time" not in s.query
