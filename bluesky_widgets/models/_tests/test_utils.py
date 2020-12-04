from bluesky_live.run_builder import build_simple_run
import numpy

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
