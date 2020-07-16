======
Design
======

These are notes for developers on the design principles of this project.

Decoupled Components
====================

Components are carefully decoupled so that anyone may take just the parts that
are useful to them and place them within existing programs or joined up with
their own custom work. For example, there are separate models for
``SearchInput`` and ``SearchResults`` which can be used and remixed
independently. These are composed to together in a ``Search`` model. Multiple
``Search`` models can be composed together in a ``SearchList`` model---for
example, to back a tabbed view of multiple searches.

In this nested scheme, parents are allowed to know about their children, but
children are not allowed to know about their parents. For example, a ``Search``
can react to and expose out things happening in ``SearchInput``, but
``SearchInput`` will never reach up into ``Search`` or sideways into its
sibling ``SearchResults``.

What does this buy us?

* Maximum reusability
* Easy embedding into existing applications, validated by early examples
  (napari, pyFAI, Xi-CAM)

Models not tied to any GUI framework
====================================

All of the logic lives in the models. The models use an internal signaling
system (vendored from napari, which in turn vendored and adapted theirs from
vispy). Thus, they are not *tied* to any particular GUI framework's signaling
system, such as Qt signals and slots or ipywidgets' traitlets, but they can be
hooked up to any of them.

For user--developer assembling components into a custom application, connecting
the models to a particular GUI looks like this, as illustrated in the examples.

.. code:: python

   thing_model = ThingModel()
   qt_thing = QtThing(thing_model)

or

.. code:: python

   thing_model = ThingModel()  # the very same type of model
   jupyter_thing = JupyterThing(thing_model)  # a different view

where, in the ``__init__`` of ``QtThing`` and ``JupyterThing``, connections are
made between Qt signals and slots or ipywidgets traitlets and the model's own
signaling system. This is in addition to whatever model--view abstractions are
happening within those frameworks; in some places one has effectively
model--model--view.

What does this buy us?

* If we launch the GUI from within IPython or Jupyter, we can access and alter
  the state of the model interactively. The model and the GUI remain synced,
  with updates propagating in both directions.

  .. code:: python

     # Update a search GUI to set the time range.
     search.input.since = "2020"
     search.input.until = "2021"
     # Access all the results.
     search.results
     # Access all the selected results.
     search.selection_as_catalog

* We can efficiently base a variety of GUI frameworks (starting with Qt and
  Jupyter) on this model because most of the work involved is simply hooking up
  the frameworks' particular signaling system to the model's.
* The model may naturally be used "headless".
* The model can be unit tested separate from any GUI-based testing.
