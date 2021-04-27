from datetime import datetime, timedelta
import pytest
from ...examples.qt_search import ExampleApp


@pytest.fixture(scope="function")
def make_test_app(qtbot, request):
    apps = []

    def actual_factory(*model_args, **model_kwargs):
        model_kwargs["show"] = model_kwargs.pop("show", request.config.getoption("--show-window"))
        app = ExampleApp(*model_args, **model_kwargs)
        apps.append(app)
        return app

    yield actual_factory

    for app in apps:
        app.close()


def test_app(make_test_app):
    "An integration test"
    app = make_test_app()
    app.searches[0].input.since = datetime(1980, 2, 2)
    app.searches[0].input.since = datetime(1985, 11, 15)
    app.searches[0].input.since = timedelta(days=-1)
