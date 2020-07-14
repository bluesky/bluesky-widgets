def pytest_addoption(parser):
    """An option to show viewers during tests. (Hidden by default).

    Showing viewers decreases test speed by about %18.  Note, due to the
    placement of this conftest.py file, you must specify the stream_widgets
    folder (in the pytest command) to use this flag.

    Example
    -------
    $ pytest stream_widgets --show-viewer
    """
    parser.addoption(
        "--show-viewer",
        action="store_true",
        default=False,
        help="don't show viewer during tests",
    )
