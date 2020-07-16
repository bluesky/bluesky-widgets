=====
Usage
=====

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

Search embedded in napari:

.. code:: bash

   pip install napari[all]
   python -m bluesky_widgets.examples.napari_dock_widgets

Search embedded in PyFAI:

.. code:: bash

   pip install pyFAI
   python -m bluesky_widgets.examples.pyFAI_dialog
