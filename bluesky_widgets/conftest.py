import importlib.util

import pytest


def pytest_addoption(parser):
    """An option to show windows during tests. (Hidden by default).

    Showing windows decreases test speed by about %18.  Note, due to the
    placement of this conftest.py file, you must specify the bluesky_widgets
    folder (in the pytest command) to use this flag.

    Example
    -------
    $ pytest bluesky_widgets --show-window
    """
    parser.addoption(
        "--show-window",
        action="store_true",
        default=False,
        help="Show window during tests (not shown by default).",
    )


def pytest_collection_modifyitems(session, config, items):
    # When the FigureView fixture returns QtFigure, inject the qtbot fixture
    # as well. This rather invasive hook is needed in order to do this late
    # enough to have access the parameterized tests but early enough to
    # actually ensure that qtbot is applied.

    if importlib.util.find_spec("qtpy"):

        from bluesky_widgets.qt.figures import QtFigure

        for item in items:
            if hasattr(item, "callspec") and "FigureView" in item.callspec.params:
                if item.callspec.params["FigureView"] is QtFigure:
                    item.fixturenames.append("qtbot")


_figure_views = []
if importlib.util.find_spec("qtpy"):

    from bluesky_widgets.qt.figures import QtFigure

    _figure_views.append(QtFigure)
if importlib.util.find_spec("ipywidgets"):

    from bluesky_widgets.jupyter.figures import JupyterFigure

    _figure_views.append(JupyterFigure)
if importlib.util.find_spec("matplotlib"):

    from bluesky_widgets.headless.figures import HeadlessFigure

    _figure_views.append(HeadlessFigure)


@pytest.fixture(params=_figure_views)
def FigureView(request):
    return request.param
