=============
API Reference
=============

.. contents::

Run Tree
========

Models
------

.. autoclass:: bluesky_widgets.models.run_tree.RunTree
   :members:

Views
-----

Qt
^^

.. autoclass:: bluesky_widgets.qt.run_tree.QtTreeView
   :members:

Plots
=====

Models
------

Figures, Axes, and Plot Entities
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: bluesky_widgets.models.plot_specs.FigureSpec
   :members:

.. autoclass:: bluesky_widgets.models.plot_specs.AxesSpec
   :members:

.. autoclass:: bluesky_widgets.models.plot_specs.LineSpec
   :members:

Base Classes
^^^^^^^^^^^^

.. autoclass:: bluesky_widgets.models.plot_specs.ArtistSpec
   :members:

.. autoclass:: bluesky_widgets.models.plot_specs.BaseSpec
   :members:

Views
-----

Qt
^^

.. autoclass:: bluesky_widgets.qt.figures.QtFigure
   :members:

.. autoclass:: bluesky_widgets.qt.figures.QtFigures
   :members:

Jupyter
^^^^^^^

.. autoclass:: bluesky_widgets.jupyter.figures.JupyterFigure
   :members:

.. autoclass:: bluesky_widgets.jupyter.figures.JupyterFigures
   :members:

Headless
^^^^^^^^

.. autoclass:: bluesky_widgets.headless.figures.HeadlessFigure
   :members:

.. autoclass:: bluesky_widgets.headless.figures.HeadlessFigures
   :members:

Plot Builders
=============

These are models which build a :class:`models.plot_specs.FigureSpec` or a list
of them. This is an example of a builder that creates one Figure:

.. code:: python

    from bluesky_widgets.models.plot_builders import RecentLines
    model = RecentLines(3, "motor", ["det"])
    model.runs  # append Runs to this list

    # Build a view by passing model.figure to any Figure view, e.g.
    from bluesky_widgets.jupyter.figures import JupyterFigure
    view = JupyterFigure(model.figure)

And this is an example of a builder that creates a list of Figures:

.. code:: python

    from bluesky_widgets.models.plot_builders import AutoRecentLines
    model = AutoRecentLines(3)
    model.runs  # append Runs to this list

    # Build a view by passing model.figures to any Figures view, e.g.
    from bluesky_widgets.jupyter.figures import JupyterFigures
    view = JupyterFigures(model.figures)

Builders with a Single Figure
-----------------------------

.. autoclass:: bluesky_widgets.models.plot_builders.RecentLines
   :members:

.. autoclass:: bluesky_widgets.models.plot_builders.Image
   :members:

Builders with a List of Figures
-------------------------------

.. autoclass:: bluesky_widgets.models.plot_builders.AutoRecentLines
   :members:

.. autoclass:: bluesky_widgets.models.plot_builders.PromptPlotter
   :members:

Streaming Utilities
===================

.. autofunction:: bluesky_widgets.utils.streaming.stream_documents_into_runs

.. autoclass:: bluesky_widgets.qt.zmq_dispatcher.RemoteDispatcher

.. autoclass:: bluesky_widgets.jupyter.zmq_dispatcher.RemoteDispatcher
