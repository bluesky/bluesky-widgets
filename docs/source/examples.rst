========
Examples
========

Example Stand-alone Qt Application
==================================

We ship some examples to illustrate what it is possible to build from this
library's components.

Stand-alone example Qt application for searching Data Broker:

.. code:: bash

   python -m bluesky_widgets.examples.qt_search

Launched from IPython, either by using ``--gui=qt`` to launch the Qt
application:

.. code:: bash

   pip install ipython
   ipython --gui=qt

.. code:: python

   from bluesky_widgets.examples.qt_search import Searches
   s  = Searches()

or using a context manager to launch the Qt application:

.. code:: bash

   ipython

.. code:: python

   from bluesky_widgets.examples.qt_search import Searches, gui_qt
   with gui_qt("example"):
       s = Searches()

Stand-alone example Qt application for viewing a run:

.. code:: bash

   python -m bluesky_widgets.examples.qt_run_tree_view

This component expects a run to be passed into it, and will then display a tree
view summarizing the contents of that run. To run this in an IPython console:

.. code:: bash

   pip install ipython
   ipython --gui=qt

.. code:: python

   from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
   from bluesky_widgets.examples.qt_run_tree_view import RunTree
   tree = RunTree()
   tree.run = get_catalog()[-1]

Embedding Components in Existing Applications
=============================================

Napari
======

Search embedded in napari as dock widget:

.. code:: bash

   pip install napari[all]
   python -m bluesky_widgets.examples.napari_dock_widgets

PyFAI
=====

Search embedded in PyFAI as a dialog box:

.. code:: bash

   pip install pyFAI
   python -m bluesky_widgets.examples.pyFAI_dialog

Xi-CAM
======

The Search component is proposed to be part of core Xi-CAM, replacing a widget
with similar functionality and appearance but different internals.

Planned Integrations
====================

The authors of bluesky-widget plan to integrate with the following open source
projects using whatever extension mechanisms they offer, and working with the
maintainers of these projects if they are interested.

* `silx view <http://www.silx.org/doc/silx/0.7.0/applications/view.html>`_
* `PyMCA <http://pymca.sourceforge.net/>`_
* `NeXpy <https://nexpy.github.io/nexpy/>`_

More welcome!
