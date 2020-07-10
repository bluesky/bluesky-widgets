=====
Goals
=====

This is a young project. Here we articulate its design principles and goals.

#. This is a library of GUI widgets, not an extensible application. There is no
   plugin architecture; there are no configuration files.
#. It ships with some runnable example applications, but it's presumed that in
   order to build something really useful to users, someone will need to write
   Python GUI code---perhaps starting by copy/pasting one of those example
   applications, or by integrating some of these widgets into an existing
   application.
#. Anything you can do with a mouse, you can do with code through a
   programmatic interface. These widgets are intended to be run alongside an
   embedded IPython console or launched within IPython or Jupyter (but they
   don't *have* to be).
#. GUI frameworks come and go faster than underlying business and science
   code, and there is a need for both web- and desktop-based solutions. From
   the start, we are building in support for multiple frameworks: Qt, Jupyter,
   and Xi-CAM (a Qt-based application with a plugin system). This ensures that
   the core logic is not tied to a specific GUI. Like the software projects
   vispy, matplotlib, and napari, we achieve this by applying the model--view
   pattern and relying on our own Event-handling system within models, rather
   than coupling to (for example) Qt signals and slots or IPython
   traitlets.
