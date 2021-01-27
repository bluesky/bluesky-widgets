from bluesky_live.run_builder import build_simple_run, RunBuilder
import numpy
import xarray
import pytest

from ..utils import call_or_eval, construct_namespace


def test_namespace():
    "Test the contents of a namespace for eval-ing expressions with a run."
    run = build_simple_run({"motor": [1, 2], "det": [10, 20]})
    namespace = construct_namespace(run, ["primary"])

    # Test entities from run....
    # the run itself
    assert eval("run", namespace) is run
    # a stream
    assert numpy.array_equal(eval("primary['motor']", namespace), numpy.array([1, 2]))
    # a field in the 'primary' stream
    assert numpy.array_equal(eval("motor", namespace), numpy.array([1, 2]))
    # numpy, three different ways
    expected = 3 + numpy.log(numpy.array([1, 2]))
    assert numpy.array_equal(eval("3 + log(motor)", namespace), expected)
    assert numpy.array_equal(eval("3 + np.log(motor)", namespace), expected)
    assert numpy.array_equal(eval("3 + numpy.log(motor)", namespace), expected)


def test_collision_with_the_name_run():
    "AHHH everything is named 'run'! The BlueskyRun should take precedence."
    with RunBuilder() as builder:
        builder.add_stream("run", data={"run": [1, 2]})
    run = builder.get_run()
    namespace = construct_namespace(run, ["run"])
    assert eval("run", namespace) is run


def test_collision_of_stream_name_and_field_name():
    "If there is a field named 'primary', the stream should take precedence."
    run = build_simple_run({"primary": [1, 2], "det": [10, 20]})
    namespace = construct_namespace(run, ["primary"])
    assert isinstance(eval("primary", namespace), xarray.Dataset)
    assert isinstance(eval("det", namespace), xarray.DataArray)


def test_collision_of_fields_across_streams():
    "The field in the stream listed first in needs_streams should take precedence."
    with RunBuilder() as builder:
        # Two streams, each with a field named "a".
        builder.add_stream("primary", data={"a": [1, 2, 3, 2, 1]})
        builder.add_stream("baseline", data={"a": [1, 1]})
    run = builder.get_run()
    namespace1 = construct_namespace(run, ["primary", "baseline"])
    # We should get run.primary.read()["a"] here.
    assert len(eval("a", namespace1)) == 5
    namespace2 = construct_namespace(run, ["baseline", "primary"])
    # We should get run.secondary.read()["a"] here.
    assert len(eval("a", namespace2)) == 2


def test_stream_omitted():
    "A stream not in `needs_stream` should have it and its fields omitted."
    with RunBuilder() as builder:
        # Two streams, each with a field named "a".
        builder.add_stream("primary", data={"a": [1, 2, 3, 2, 1]})
        builder.add_stream("baseline", data={"b": [1, 1]})
    run = builder.get_run()
    namespace = construct_namespace(run, ["baseline"])
    assert "a" not in namespace
    assert "primary" not in namespace
    assert "baseline" in namespace
    assert "b" in namespace


def test_names_with_spaces():
    "Names with spaces cannot be eval-ed, but they can be looked up."
    with RunBuilder() as builder:
        # Two streams, each with a field named "a".
        builder.add_stream("some stream", data={"some field": [1, 2, 3, 2, 1]})
    run = builder.get_run()
    namespace = construct_namespace(run, ["some stream"])
    assert "some stream" in namespace
    assert "some field" in namespace


def test_call_or_eval_errors():
    "Test that various failrue modes raise expected errors."
    run = build_simple_run({"motor": [1, 2], "det": [10, 20]})
    with pytest.raises(ValueError, match=".*callable or string.*"):
        call_or_eval({"x": 1}, run, ["primary"])
    with pytest.raises(ValueError, match=".*parse.*"):
        call_or_eval({"x": "invalid***syntax"}, run, ["primary"])
    with pytest.raises(ValueError, match=".*evaluate.*"):
        call_or_eval({"x": "missing_key"}, run, ["primary"])


def test_call_or_eval_with_user_namespace():
    "Test that user-injected items in the namespace are found."
    run = build_simple_run({"motor": [1, 2], "det": [10, 20]})
    thing = object()
    result = call_or_eval({"x": "thing"}, run, [], namespace={"thing": thing})
    assert result["x"] is thing


def test_call_or_eval_magical_signature_inspection():
    "Test magical signature inspection."
    run = build_simple_run({"motor": [1, 2], "det": [10, 20]})

    def func1(motor, det):
        "Access fields by name."
        return motor + det

    result = call_or_eval({"x": func1}, run, ["primary"])
    assert numpy.array_equal(result["x"], [11, 22])

    def func2(primary):
        "Access a stream by name."
        return primary["motor"]

    result = call_or_eval({"x": func2}, run, ["primary"])
    assert numpy.array_equal(result["x"], [1, 2])

    def func3(does_not_exist):
        "Test a missing variable."
        ...

    with pytest.raises(ValueError, match="Cannot find match for.*"):
        call_or_eval({"x": func3}, run, ["primary"])

    def func4(thing):
        "Test an item in the user-provided namespace."
        return thing

    thing = object()
    result = call_or_eval({"x": func4}, run, [], namespace={"thing": thing})
    assert result["x"] is thing
