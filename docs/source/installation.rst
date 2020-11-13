============
Installation
============

This project currently has no *required* dependencies. The libraries you need
will depend on which graphical frontend(s) you plan to use.

We recommend to upgrade ``pip`` and ``setuptools`` first, as recent versions of
these specifically make installing what follows tend to succeed better.:::

    $ pip install --upgrade pip setuptools

The examples perform data generation and access using some bluesky projects:::

    $ pip install suitcase-msgpack bluesky databroker ophyd

and they use Qt:::
    
    $ pip install qtpy pyqt5

Finally, install the project itself:::

    $ pip install bluesky-widgets
