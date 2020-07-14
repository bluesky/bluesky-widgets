=====
Usage
=====

You can run the example application in multiple ways:

* as a stand-alone application
* from within IPython
* embedded within napari
* as a Xi-CAM plugin (TODO)
* embedded with PyDM (TODO)

Stand-alone Qt application:

.. code:: bash

   python -m stream_widgets.examples.qt_bec

Launched from IPython, either by using ``--gui=qt`` to launch the Qt
application:

.. code:: bash

   pip install ipython
   ipython --gui=qt

.. code:: python

   from stream_widgets.examples.qt_bec import Viewer
   viewer = Viewer()

or using a context manager to launch the Qt application:

.. code:: bash

   ipython

.. code:: python

   from stream_widgets.examples.qt_bec import Viewer, gui_qt
   with gui_qt("example"):
       viewer = Viewer()

Embedded in napari:

.. code:: bash

   pip install napari[all]
   python -m stream_widgets.examples.napari_dock_widgets

TODO Xi-CAM

TODO PyDM
