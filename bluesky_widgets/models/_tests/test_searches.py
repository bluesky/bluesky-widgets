from ..search import Search, SearchList


def test_search_list_mutually_exclusive_active_item():
    search_list = SearchList()
    s1 = Search({}, columns=())
    s2 = Search({}, columns=())
    search_list.extend([s1, s2])
    s1.active = False
    s2.active = False
    assert search_list.active is None
    s1.active = True
    assert s1.active
    assert not s2.active
    assert search_list.active is s1
    s2.active = True
    assert not s1.active
    assert s2.active
    assert search_list.active is s2
    s2.active = False
    assert search_list.active is None
    assert "SearchList" in repr(search_list)


def test_search():
    s = Search({}, columns=(), name="test")
    assert s.name == "test"
    assert not s.breadcrumbs
    assert s.root_catalog is s.current_catalog
    assert s.run_search is None
    assert s.results is None
    assert s.input is None
    assert s.active is False
    assert s.active_run is None
