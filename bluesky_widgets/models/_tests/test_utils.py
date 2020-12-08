from bluesky_live.run_builder import build_simple_run, RunBuilder
import numpy
import xarray

from ..utils import construct_namespace


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
