===============
Release History
===============

v0.0.16 (2024-03-21)
====================

Added
-----

- ``queue-monitor`` app: menu items to save plan history to TXT, JSON and YAML files.


v0.0.15 (2023-06-28)
====================

Added
-----

- ``Auto`` checkbox in ``Queue`` widgets to enable AUTOSTART mode.

- AUTOSTART mode is displayed in the status monitor widget.

- ``Pause`` button is now enabled whenever Run Engine is in the running state.

- ``Ctrl-C`` button in ``Plan Execution`` widgets for sending interrupts to IPython kernel.

- ``Update Environment`` button in ``RUNNING PLAN`` widgets, which initiates generation of
  new lists of existing and allowed plans and devices based on contents of the worker namespace.


v0.0.14 (2022-11-17)
====================

Changed
-------

- No wait for completion of operations ``Pause: Deferred`` and ``Pause: Immediate``.
  GUI remains unblocked.

- The default group name used for user group permissions is changed from hardcoded
  ``admin`` to the group name used by default by ``bluesky-queueserver-api`` package
  (``primary``).

Fixed
-----

- Behavior of the ``Stop`` button (request/cancel stopping the queue). The button
  is now fully functional.


v0.0.13 (2022-08-01)
====================

Changed
-------

- Renamed parameters of ``RunEngineClient`` model to ``zmq_control_addr`` and ``zmq_info_addr``
  (this may break existing code).
- Renamed CLI parameters of ``queue-monitor`` to ``--zmq-control-addr`` and ``--zmq-info-addr``.
  Old parameters are still supported.
- Renamed environment variables used to set addresses to ``QSERVER_ZMQ_CONTROL_ADDRESS`` and ``QSERVER_ZMQ_INFO_ADDRESS``.
  Old environment variables are still supported.
- ``RunEngineClient`` is now using ``bluesky-queueserver-api`` package instead of raw API to communicate
  with the Queue Server. The raw API calls were directly replaced with the equivalent API from the package,
  so the changes are not expected to influence functionality of the widgets. The code may be further changed
  in the future to utilized `bluesky-queueserver-api` features more efficiently.
- ``RunEngineClient`` model was slightly modified to accept initialization parameters ``http_server_uri``
  and ``http_server_api_key``, which are necessary for communication with Queue Server over HTTP
  (supported by ``bluesky-queueserver-api`` package).
- ``queue-monitor`` demo application was modified to support HTTP communication. HTTP server URI
  is set using ``--http-server-uri`` CLI parameter or ``QSERVER_HTTP_SERVER_URI`` environment variable.
  API key is set using ``QSERVER_HTTP_SERVER_API_KEY`` environment variable.
- Set 'tight layout' for Matplotlib figures (``QtFigure``), which significantly reduces wasted screen space,
  especially if plots contain colorbars.

Added
-----

- New ``QtFigures._on_active_index_changed()`` event handler that allows to programmatically activate
  a tab by setting ``FigureList.active_index``.
- Implemented an option to show colorbars for image plots. New boolean parameter ``show_colorbar``
  of ``RasteredImages.__init__()`` enables/disables colorbars for the created image plots. The ``RasteredImages.show_colorbar``
  property changes the setting for the future plots (not the images that are being plotted).


v0.0.12 (2022-04-05)
====================

Added
-----

- RE Manager Widgets: the list of available plans in the combo box of plan editor
  is now automatically updated when it is changed at the server.

v0.0.11 (2022-03-23)
====================

Added
-----

- Configuration options for ``Batch Upload`` dialog box that allow
  to set up additional parameters for custom function that generates
  a batch of plans from a custom spreadsheet.
- An application for monitoring and controlling the queue. The application
  may be started using ``queue-monitor`` endpoint.

Fixed
-----

- Fixed a bug (typo) that caused the application to wait indefinitely for
  the RE environment to open in case startup script raised an exception
  (operation failed at the server).

v0.0.10 (2021-10-08)
====================

Fixed
-----

- Plans with only ``args`` or ``kwargs`` as parameters can now be
  submitted properly in the plan editor widget (#152).
- Updated the examples to use proper imports and fixed the use
  of a deprecated napari method (#154).
- Increased the timer for recieving data in the zmq dispatcher
  to prevent high memory and CPU usage (#150).

Initial Release (2020-07-17)
============================
