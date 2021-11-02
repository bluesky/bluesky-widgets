from bluesky_live.run_builder import build_simple_run

from .. import AutoLines
from ....headless.figures import HeadlessFigures


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
    "Test AutoLines with 'pinned' and un-pinned runs."
    NUM_YS = 2
    model = AutoLines(max_runs=MAX_RUNS)
    view = HeadlessFigures(model.figures)
    assert not model.figures

    # Add MAX_RUNS and then some more and check that they do get bumped off.
    for run in runs[:5]:
        model.add_run(run)
        assert len(model.plot_builders[0].runs) <= MAX_RUNS
    assert runs[2:5] == list(model.plot_builders[0].runs)
    assert len(model.figures) == 1

    # Add a pinned run.
    pinned_run = runs[5]
    model.add_run(pinned_run, pinned=True)
    assert frozenset([pinned_run.metadata["start"]["uid"]]) == model.plot_builders[0].pinned
    for run in runs[6:]:
        model.add_run(run)
        assert len(model.plot_builders[0].runs) == 1 + MAX_RUNS
        for axes_index in range(NUM_YS):
            assert len(model.figures[0].axes[axes_index].artists) == (1 + MAX_RUNS)
    # Check that it hasn't been bumped off.
    assert pinned_run in model.plot_builders[0].runs
    assert len(model.figures) == 1

    # Remove the pinned run.
    model.discard_run(pinned_run)
    assert len(model.plot_builders[0].runs) == MAX_RUNS
    for axes_index in range(NUM_YS):
        assert len(model.figures[0].axes[axes_index].artists) == MAX_RUNS
    assert pinned_run not in model.plot_builders[0].runs

    view.close()


def test_decrease_max_runs():
    "Decreasing max_runs should remove the runs and their associated lines."
    INITIAL_MAX_RUNS = 5
    model = AutoLines(max_runs=INITIAL_MAX_RUNS)
    view = HeadlessFigures(model.figures)
    for run in runs[:5]:
        model.add_run(run)
    assert len(model.plot_builders[0].runs) == INITIAL_MAX_RUNS
    assert len(model.figures[0].axes[0].artists) == INITIAL_MAX_RUNS
    # Decrease max_runs.
    model.max_runs = MAX_RUNS
    assert len(model.plot_builders[0].runs) == MAX_RUNS
    assert len(model.figures[0].axes[0].artists) == MAX_RUNS

    view.close()


def test_removed_figures():
    "Test that a new figure is created after closing a tab/removing a figure."
    model = AutoLines(max_runs=MAX_RUNS)
    view = HeadlessFigures(model.figures)
    model.add_run(runs[0])  # One figure, 3 plot_builders
    assert len(model.plot_builders) == 3
    assert len(model.figures) == 1
    # Remove the figure. No figures or plot_builders should be left.
    del model.figures[0]
    assert len(model.plot_builders) == 0
    assert len(model.figures) == 0
    # Add the runs back and a new figure should be created.
    model.add_run(runs[0])
    assert len(model.plot_builders) == 3
    assert len(model.figures) == 1

    view.close()
