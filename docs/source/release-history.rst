===============
Release History
===============

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
