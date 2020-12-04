from ..plot_builders import RecentLines
from bluesky_live.run_builder import build_simple_run


def test_pinning():
    # Make some runs to use.
    runs = [
        build_simple_run(
            {"motor": [1, 2], "det": [10, 20]}, metadata={"scan_id": 1 + i}
        )
        for i in range(10)
    ]
    MAX_RUNS = 3
    model = RecentLines(MAX_RUNS, "motor", ["det"])

    # Add MAX_RUNS and then some more and check that they do get bumped off.
    for run in runs[:5]:
        model.add_run(run)
        assert len(model.runs) <= MAX_RUNS
    assert runs[2:5] == list(model.runs)

    # Add a pinned run.
    pinned_run = runs[5]
    model.add_run(pinned_run, pinned=True)
    assert frozenset([pinned_run.metadata["start"]["uid"]]) == model.pinned
    for run in runs[5:]:
        model.add_run(run)
        assert len(model.runs) == 1 + MAX_RUNS
    # Check that it hasn't been bumpbed off.
    assert pinned_run in model.runs
