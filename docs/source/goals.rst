=====
Goals
=====

This is a young project. Here we articulate its design principles and goals.

#. This is a library of reusable Graphic User Interface (GUI) components, not
   an extensible application. There is no plugin architecture; there are no
   configuration files.
#. It ships with some runnable example applications, but it's presumed that in
   order to build something really useful to users, someone will need to write
   Python GUI code---perhaps starting by copy/pasting one of those example
   applications, or by integrating some of these widgets into an existing
   application.
#. Anything you can do with a mouse, you can do with code through a
   programmatic interface. These widgets are intended to be run alongside an
   embedded IPython console or launched within IPython or Jupyter (but they
   don't *have* to be).
#. There is a need for both web- and desktop-based solutions, and the space of
   GUI frameworks is ever-changing, especially on the web. From the start, we
   are building in front-ends for Qt and Jupyter with examples of how to embed
   these components in the existing Qt applications such as Xi-CAM, PyFAI,
   PyMca, napari, and PyDM, using their respective extension points.
