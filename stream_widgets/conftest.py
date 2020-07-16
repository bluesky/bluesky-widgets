def pytest_addoption(parser):
    """An option to show windows during tests. (Hidden by default).

    Showing windows decreases test speed by about %18.  Note, due to the
    placement of this conftest.py file, you must specify the stream_widgets
    folder (in the pytest command) to use this flag.

    Example
    -------
    $ pytest stream_widgets --show-window
    """
    parser.addoption(
        "--show-window",
        action="store_true",
        default=False,
        help="Show window during tests (not shown by default).",
    )
