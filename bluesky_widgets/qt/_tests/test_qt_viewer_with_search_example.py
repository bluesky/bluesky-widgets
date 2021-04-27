import pytest
from ...examples.advanced.qt_viewer_with_search import ExampleApp


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
    assert not app.viewer.figures
    app.searches[0].input.query = {"plan_name": "scan"}
    # TODO It would be nice to hit the "View Selected Runs" button here, but
    # changing *selection* from the model is not supported.
    # https://github.com/bluesky/bluesky-widgets/issues/41
    catalog = app.searches[0].run_search.search_results.catalog
    assert len(catalog)  # Results should be non-empty
    for _, run in catalog.items():
        app.viewer.add_run(run)
    assert app.viewer.figures
    assert app.viewer.figures[0].axes[0].artists
    app.viewer.figures.clear()
