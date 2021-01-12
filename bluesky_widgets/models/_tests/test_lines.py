from bluesky_live.run_builder import build_simple_run
import pytest

from ..plot_builders import Lines
from ..plot_specs import AxesSpec, FigureSpec
from ...headless.figures import HeadlessFigure


# Make some runs to use.
runs = [
    build_simple_run(
        {"motor": [1, 2], "det": [10, 20], "det2": [15, 25]},
        metadata={"scan_id": 1 + i},
    )
    for i in range(10)
]
MAX_RUNS = 3


def test_pinned():
    "Test Lines with 'pinned' and un-pinned runs."
    ys = ["det", "det2"]
    num_ys = len(ys)
    model = Lines("motor", ys, max_runs=MAX_RUNS)
    view = HeadlessFigure(model.figure)

    # Add MAX_RUNS and then some more and check that they do get bumped off.
    for run in runs[:5]:
        model.add_run(run)
        assert len(model.runs) <= MAX_RUNS
    assert runs[2:5] == list(model.runs)

    # Add a pinned run.
    pinned_run = runs[5]
    model.add_run(pinned_run, pinned=True)
    assert frozenset([pinned_run.metadata["start"]["uid"]]) == model.pinned
    for run in runs[6:]:
        model.add_run(run)
        assert len(model.runs) == 1 + MAX_RUNS
        assert len(model.figure.axes[0].lines) == num_ys * (1 + MAX_RUNS)
    # Check that it hasn't been bumped off.
    assert pinned_run in model.runs

    # Remove the pinned run.
    model.discard_run(pinned_run)
    assert len(model.runs) == MAX_RUNS
    assert len(model.figure.axes[0].lines) == num_ys * MAX_RUNS
    assert pinned_run not in model.runs

    view.close()


def test_properties():
    "Touch various accessors"
    model = Lines("c * motor", ["det"], namespace={"c": 3}, max_runs=MAX_RUNS)
    view = HeadlessFigure(model.figure)
    model.add_run(runs[0])
    assert model.runs[0] is runs[0]
    assert model.max_runs == MAX_RUNS
    assert model.x == "c * motor"
    assert model.ys == ("det",)
    assert dict(model.namespace) == {"c": 3}
    assert model.needs_streams == ("primary",)
    assert model.pinned == frozenset()

    view.close()


def test_decrease_max_runs():
    "Decreasing max_runs should remove the runs and their associated lines."
    INITIAL_MAX_RUNS = 5
    model = Lines("motor", ["det"], namespace={"c": 3}, max_runs=INITIAL_MAX_RUNS)
    view = HeadlessFigure(model.figure)
    for run in runs[:5]:
        model.add_run(run)
    assert len(model.runs) == INITIAL_MAX_RUNS
    assert len(model.figure.axes[0].lines) == INITIAL_MAX_RUNS
    # Decrease max_runs.
    model.max_runs = MAX_RUNS
    assert len(model.runs) == MAX_RUNS
    assert len(model.figure.axes[0].lines) == MAX_RUNS

    view.close()


@pytest.mark.parametrize("expr", ["det / det2", "-log(det)", "np.sqrt(det)"])
def test_expressions(expr):
    "Test Lines with 'pinned' and un-pinned runs."
    ys = [expr]
    model = Lines("motor", ys, max_runs=MAX_RUNS)
    view = HeadlessFigure(model.figure)
    model.add_run(runs[0])
    assert len(model.figure.axes[0].lines) == 1

    view.close()


@pytest.mark.parametrize(
    "func",
    [
        lambda det, det2: det / det2,
        lambda det, log: -log(det),
        lambda det, np: np.sqrt(det),
    ],
)
def test_functions(func):
    "Test Lines with 'pinned' and un-pinned runs."
    ys = [func]
    model = Lines("motor", ys, max_runs=MAX_RUNS)
    view = HeadlessFigure(model.figure)
    model.add_run(runs[0])
    assert len(model.figure.axes[0].lines) == 1

    view.close()


def test_figure_set_after_instantiation():
    axes = AxesSpec()
    model = Lines("motor", [], axes=axes)
    assert model.figure is None
    figure = FigureSpec((axes,), title="")
    assert model.figure is figure
    view = HeadlessFigure(model.figure)
    view.close()
