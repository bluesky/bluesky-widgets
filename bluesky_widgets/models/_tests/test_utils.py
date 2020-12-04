from bluesky_live.run_builder import build_simple_run, RunBuilder
import numpy
import xarray

from ..utils import construct_namespace


def test_namespace():
    "Test the contents of a namespace for eval-ing expressions with a run."
    run = build_simple_run({"motor": [1, 2], "det": [10, 20]})
    namespace = construct_namespace(run)

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


def test_shadowing_of_run():
    "AHHH everything is named 'run'! The BlueskyRun should take precedence."
    with RunBuilder() as builder:
        builder.add_stream("run", data={"run": [1, 2]})
    run = builder.get_run()
    namespace = construct_namespace(run)
    assert eval("run", namespace) is run


def test_shadowing_of_stream():
    "If there is a field named 'primary', the stream should take precedence."
    run = build_simple_run({"primary": [1, 2], "det": [10, 20]})
    namespace = construct_namespace(run)
    assert isinstance(eval("primary", namespace), xarray.Dataset)
    assert isinstance(eval("det", namespace), xarray.DataArray)
