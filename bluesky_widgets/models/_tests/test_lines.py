from bluesky_live.run_builder import build_simple_run
import pytest

from ..plot_builders import Lines
from ..plot_specs import Axes, Figure


# Make some runs to use.
runs = [
    build_simple_run(
        {"motor": [1, 2], "det": [10, 20], "det2": [15, 25]},
        metadata={"scan_id": 1 + i},
    )
    for i in range(10)
]
MAX_RUNS = 3


def test_pinned(FigureView):
    "Test Lines with 'pinned' and un-pinned runs."
    ys = ["det", "det2"]
    num_ys = len(ys)
    model = Lines("motor", ys, max_runs=MAX_RUNS)
    view = FigureView(model.figure)

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
        assert len(model.figure.axes[0].artists) == num_ys * (1 + MAX_RUNS)
    # Check that it hasn't been bumped off.
    assert pinned_run in model.runs

    # Remove the pinned run.
    model.discard_run(pinned_run)
    assert len(model.runs) == MAX_RUNS
    assert len(model.figure.axes[0].artists) == num_ys * MAX_RUNS
    assert pinned_run not in model.runs

    view.close()


def test_properties(FigureView):
    "Touch various accessors"
    model = Lines("c * motor", ["det"], namespace={"c": 3}, max_runs=MAX_RUNS)
    view = FigureView(model.figure)
    model.add_run(runs[0])
    assert model.runs[0] is runs[0]
    assert model.max_runs == MAX_RUNS
    assert model.x == "c * motor"
    assert list(model.ys) == ["det"]
    assert dict(model.namespace) == {"c": 3}
    assert model.needs_streams == ("primary",)
    assert model.pinned == frozenset()

    view.close()


@pytest.mark.parametrize(
    "operation,operation_args,num_ys,ys_list,num_lines",
    [
        ("append", ("det+1",), 2, ["det", "det+1"], 2),
        ("extend", (["det+1"],), 2, ["det", "det+1"], 2),
        ("insert", (0, "det+1"), 2, ["det+1", "det"], 2),
        ("insert", (1, "det+1"), 2, ["det", "det+1"], 2),
    ],
)
def test_adding_ys(operation, operation_args, num_ys, ys_list, num_lines, FigureView):
    "Test that append, extend, and insert work properly"
    model = Lines("c * motor", ["det"], namespace={"c": 3}, max_runs=MAX_RUNS)
    view = FigureView(model.figure)
    model.add_run(runs[0])
    assert len(model.ys) == 1
    assert list(model.ys) == ["det"]
    assert len(model.figure.axes[0].artists) == 1
    getattr(model.ys, operation)(*operation_args)
    assert len(model.ys) == num_ys
    assert list(model.ys) == ys_list
    assert len(model.figure.axes[0].artists) == num_lines
    view.close()


@pytest.mark.parametrize(
    "operation,operation_args,num_ys,ys_list,num_lines",
    [
        ("remove", ("det+1",), 2, ["det", "det+2"], 2),
        ("pop", (), 2, ["det", "det+1"], 2),
        ("pop", (1,), 2, ["det", "det+2"], 2),
        ("clear", (), 0, [], 0),
    ],
)
def test_removing_ys(operation, operation_args, num_ys, ys_list, num_lines, FigureView):
    "Test that remove, pop, del, and clear work properly"
    model = Lines("c * motor", ["det", "det+1", "det+2"], namespace={"c": 3}, max_runs=MAX_RUNS)
    view = FigureView(model.figure)
    model.add_run(runs[0])
    assert len(model.ys) == 3
    assert list(model.ys) == ["det", "det+1", "det+2"]
    assert len(model.figure.axes[0].artists) == 3
    getattr(model.ys, operation)(*operation_args)
    assert len(model.ys) == num_ys
    assert list(model.ys) == ys_list
    assert len(model.figure.axes[0].artists) == num_lines
    view.close()


def test_decrease_max_runs(FigureView):
    "Decreasing max_runs should remove the runs and their associated lines."
    INITIAL_MAX_RUNS = 5
    model = Lines("motor", ["det"], namespace={"c": 3}, max_runs=INITIAL_MAX_RUNS)
    view = FigureView(model.figure)
    for run in runs[:5]:
        model.add_run(run)
    assert len(model.runs) == INITIAL_MAX_RUNS
    assert len(model.figure.axes[0].artists) == INITIAL_MAX_RUNS
    # Decrease max_runs.
    model.max_runs = MAX_RUNS
    assert len(model.runs) == MAX_RUNS
    assert len(model.figure.axes[0].artists) == MAX_RUNS

    view.close()


@pytest.mark.parametrize("expr", ["det / det2", "-log(det)", "np.sqrt(det)"])
def test_expressions(expr, FigureView):
    "Test Lines with 'pinned' and un-pinned runs."
    ys = [expr]
    model = Lines("motor", ys, max_runs=MAX_RUNS)
    view = FigureView(model.figure)
    model.add_run(runs[0])
    assert len(model.figure.axes[0].artists) == 1

    view.close()


@pytest.mark.parametrize(
    "func",
    [
        lambda det, det2: det / det2,
        lambda det, log: -log(det),
        lambda det, np: np.sqrt(det),
    ],
    ids=["division", "top-level-log", "np-dot-log"],
)
def test_functions(func, FigureView):
    "Test Lines with 'pinned' and un-pinned runs."
    ys = [func]
    model = Lines("motor", ys, max_runs=MAX_RUNS)
    view = FigureView(model.figure)
    model.add_run(runs[0])
    assert len(model.figure.axes[0].artists) == 1

    view.close()


def test_figure_set_after_instantiation(FigureView):
    axes = Axes()
    model = Lines("motor", [], axes=axes)
    assert model.figure is None
    figure = Figure((axes,), title="")
    assert model.figure is figure
    view = FigureView(model.figure)
    view.close()


@pytest.mark.parametrize(
    "test_x_label,expected_x_label",
    [
        (None, "motor"),
        ("test", "test"),
    ],
)
def test_x_label(test_x_label, expected_x_label, FigureView):
    "Test that Lines properly sets the x_label."
    axes = Axes(x_label=test_x_label)
    model = Lines("motor", ["det"], axes=axes)
    figure = Figure((axes,), title="")
    view = FigureView(model.figure)
    assert model.axes.x_label == expected_x_label
    assert figure.axes[0].x_label == expected_x_label
    assert view.figure.axes[0].get_xlabel() == expected_x_label
    view.close()


@pytest.mark.parametrize(
    "test_y_labels,expected_y_labels",
    [
        ([None, "test"], ["det", "det, det+1", "test", "test"]),
        (["test", ""], ["test", "test", "", ""]),
        (["", None], ["", "", "det, det+1", "det, det+1, det+2"]),
    ],
)
def test_y_label(test_y_labels, expected_y_labels, FigureView):
    "Test that Lines correctly sets and updates the y_label."
    axes = Axes(y_label=test_y_labels[0])
    model = Lines("motor", ["det"], axes=axes)
    figure = Figure((axes,), title="")
    view = FigureView(model.figure)
    assert model.y_label == model.axes.y_label == expected_y_labels[0]
    assert figure.axes[0].y_label == expected_y_labels[0]
    assert view.figure.axes[0].get_ylabel() == expected_y_labels[0]
    model.ys.append("det+1")
    assert model.y_label == model.axes.y_label == expected_y_labels[1]
    assert figure.axes[0].y_label == expected_y_labels[1]
    assert view.figure.axes[0].get_ylabel() == expected_y_labels[1]
    model.y_label = test_y_labels[1]
    assert model.y_label == model.axes.y_label == expected_y_labels[2]
    assert figure.axes[0].y_label == expected_y_labels[2]
    assert view.figure.axes[0].get_ylabel() == expected_y_labels[2]
    model.ys.append("det+2")
    assert model.y_label == model.axes.y_label == expected_y_labels[3]
    assert figure.axes[0].y_label == expected_y_labels[3]
    assert view.figure.axes[0].get_ylabel() == expected_y_labels[3]

    view.close()


@pytest.mark.parametrize(
    "test_titles,expected_titles",
    [
        ([None, "test"], ["det v motor", "det, det+1 v motor", "test", "test"]),
        (["test", ""], ["test", "test", "", ""]),
        (["", None], ["", "", "det, det+1 v motor", "det, det+1, det+2 v motor"]),
    ],
)
def test_title(test_titles, expected_titles, FigureView):
    "Test that Lines correctly sets and updates the y_label."
    axes = Axes(title=test_titles[0])
    model = Lines("motor", ["det"], axes=axes)
    figure = Figure((axes,), title="")
    view = FigureView(model.figure)
    assert model.title == model.axes.title == expected_titles[0]
    assert figure.axes[0].title == expected_titles[0]
    assert view.figure.axes[0].get_title() == expected_titles[0]
    model.ys.append("det+1")
    assert model.title == model.axes.title == expected_titles[1]
    assert figure.axes[0].title == expected_titles[1]
    assert view.figure.axes[0].get_title() == expected_titles[1]
    model.title = test_titles[1]
    assert model.title == model.axes.title == expected_titles[2]
    assert figure.axes[0].title == expected_titles[2]
    assert view.figure.axes[0].get_title() == expected_titles[2]
    model.ys.append("det+2")
    assert model.title == model.axes.title == expected_titles[3]
    assert figure.axes[0].title == expected_titles[3]
    assert view.figure.axes[0].get_title() == expected_titles[3]

    view.close()
