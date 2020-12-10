import ast
import contextlib
import inspect

import numpy

from ..utils.list import EventedList


class RunList(EventedList):
    """
    A list of BlueskyRuns.
    """

    __slots__ = ()

    def __contains__(self, run):
        uid = run.metadata["start"]["uid"]
        for run_ in self:
            if run_.metadata["start"]["uid"] == uid:
                return True
        else:
            return False


def run_is_completed(run):
    "True is Run is completed and no further updates are coming."
    return run.metadata["stop"] is not None


def run_is_live(run):
    "True if Run is 'live' (observable) based on a streaming source, not at rest."
    return hasattr(run, "events")


def run_is_live_and_not_completed(run):
    "True if Run is 'live' (observable) and not yet complete."
    return run_is_live(run) and (not run_is_completed(run))


@contextlib.contextmanager
def lock_if_live(run):
    """
    Lock to prevent new data from being added, if this is a 'live' BlueskyRun.

    If it is a BlueskyRun backed by data at rest (i.e. from databroker) do
    nothing.
    """
    if run_is_live(run):
        with run.write_lock:
            yield
    else:
        yield


# Make numpy functions accessible as (for example) log, np.log, and numpy.log.
_base_namespace = {"numpy": numpy, "np": numpy}
_base_namespace.update({name: getattr(numpy, name) for name in numpy.__all__})


def construct_namespace(run, stream_names):
    """
    Put the contents of a run into a namespace to lookup in or ``eval`` expressions in.

    This is used by the plot builders to support usages like

    >>> model = RecentLines(3, "-motor", ["log(det)"])

    The words available in these expressions include:

    * The ``BlueskyRun`` itself, as ``"run"``, from which any data or metadata
      can be obtained
    * All the streams, with the data accessible as items in a dict, as in
      ``"primary['It']"`` or ``"baseline['motor']"``
    * The columns in the streams given by stream_names, as in ``"I0"``. If a
      column name appears in multiple streams, the streams earlier in the list
      get precedence.
    * All functions in numpy. They can be spelled as ``log``, ``np.log``, or
      ``numpy.log``

    In the event of name collisions, items higher in the list above will get
    precedence.

    Parameters
    ----------
    run : BlueskyRun
    stream_names : List[String]

    Returns
    -------
    namespace : Dict
    """
    namespace = dict(_base_namespace)  # shallow copy
    with lock_if_live(run):
        # Add columns from streams in stream_names. Earlier entries will get
        # precedence.
        for stream_name in reversed(stream_names):
            ds = run[stream_name].to_dask()
            namespace.update({column: ds[column] for column in ds})
            namespace.update({column: ds[column] for column in ds.coords})
        namespace.update(
            {stream_name: run[stream_name].to_dask() for stream_name in stream_names}
        )
    namespace.update({"run": run})
    return namespace


class BadExpression(Exception):
    pass


def call_or_eval(items, run, stream_names, namespace=None):
    """
    Given a mix of callables and string expressions, call or eval them.

    Parameters
    ----------
    items : List[String | Callable]
        Each item must be a stream name, field name, a valid Python
        expression, or a callable. The signature of the callable may include
        any valid Python identifiers provideed by :func:`construct_namespace`
        or the user-provided namespace parmeter below. See examples.
    run : BlueskyRun
    stream_names : List[String]
    namespace : Dict, optional

    Returns
    -------
    results : List[Any]

    Raises
    ------
    ValueError
        If input is not String or Callable
    BadExpression
        If input is String and eval(...) raises an error

    Examples
    --------

    A function can have access to the whole BlueskyRun.

    >>> def f(run):
    ...     ds = run.primary.read()
    ...     return (ds["a"] - ds["b"]) / (ds["a"] + ds["b"])
    ...
    >>> call_or_eval([f], run, ["primary"])

    But, it also provides a more "magical" option in support of brevity.
    The signature may include parameters with the names streams or fields. The
    names in the signature are significant and will determine what parameters
    the function is called with.

    >>> def f(a, b):
    ...     return (a - b) / (a + b)
    ...
    >>> call_or_eval([f], run, ["primary"])

    Equivalently, as a lambda function:
    >>> call_or_eval([lambda a, b: (a - b) / (a + b)], run, ["primary"])
    """
    with lock_if_live(run):
        namespace_ = construct_namespace(run, stream_names)
        # Overlay user-provided namespace.
        namespace_.update(namespace or {})
        del namespace  # Avoid conflating namespace and namespace_ below.
        results = []
        for item in items:
            # If it is a callable, call it.
            if callable(item):
                # Inspect the callable's signature. For each parameter, find an
                # item in our namespace with a matching name. This is similar
                # to the "magic" of pytest fixtures.
                parameters = inspect.signature(item).parameters
                kwargs = {}
                for name, parameter in parameters.items():
                    try:
                        kwargs[name] = namespace_[name]
                    except KeyError:
                        if parameter.default is parameter.empty:
                            raise ValueError(f"Cannot find match for parameter {name}")
                        # Otherwise, it's an optional parameter, so skip it.
                results.append(item(**kwargs))
            elif isinstance(item, str):
                # If it is a key in our namespace, look it up.
                try:
                    # This handles field or stream names that are not valid
                    # Python identifiers (e.g. ones with spaces in them).
                    results.append(namespace_[item])
                    continue
                except KeyError:
                    pass
                # Check whether it is valid Python syntax.
                try:
                    ast.parse(item)
                except SyntaxError as err:
                    raise ValueError(
                        f"Could find {item!r} in namespace or parse it as "
                        "a Python expression."
                    ) from err
                # Try to evaluate it as a Python expression in the namespace.
                try:
                    results.append(eval(item, namespace_))
                except Exception as err:
                    raise ValueError(
                        f"Could find {item!r} in namespace or evaluate it."
                    ) from err
            else:
                raise ValueError(
                    f"expected callable or string, received {item!r} of "
                    f"type {type(item).__name__}"
                )
    return results


def auto_label(callable_or_expr):
    """
    Given a callable or a string, extract a name for labeling axes.

    Parameters
    ----------
    callable_or_expr : String | Callable

    Returns
    -------
    label : String
    """
    if callable(callable_or_expr):
        return getattr(callable_or_expr, "__name__", repr(callable_or_expr))
    elif isinstance(callable_or_expr, str):
        return callable_or_expr
    else:
        raise ValueError(
            f"expected callable or string, received {callable_or_expr!r} of "
            f"type {type(callable_or_expr).__name__}"
        )
