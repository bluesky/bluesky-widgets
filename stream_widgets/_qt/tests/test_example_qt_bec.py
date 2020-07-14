from datetime import datetime


def test_viewer(make_test_viewer):
    make_test_viewer()


def test_manipulating_times(make_test_viewer):
    viewer = make_test_viewer()
    viewer.searches[0].input.since = 0
    viewer.searches[0].input.since = datetime(1985, 11, 15)
    viewer.searches[0].input.until = datetime(1985, 11, 15)
