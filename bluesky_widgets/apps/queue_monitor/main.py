import argparse
import os

from bluesky_widgets.qt import gui_qt

from .viewer import Viewer
from .settings import SETTINGS


def main(argv=None):
    parser = argparse.ArgumentParser(description="BlueSky Queue Monitor")
    parser.add_argument(
        "--zmq-control",
        help="Address of control socket of RE Manager. If the address "
        "is passed as a CLI parameter, it overrides the address specified with "
        "QSERVER_ZMQ_CONTROL_ADDRESS environment variable.",
    )
    parser.add_argument(
        "--zmq-publish",
        help="Address of PUB-SUB socket of RE Manager. If the address "
        "is passed as a CLI parameter, it overrides the address specified with "
        "QSERVER_ZMQ_PUBLISH_ADDRESS environment variable.",
    )
    args = parser.parse_args(argv)

    # The priority is first to check if an address is passed as a parameter and then
    #   check if the environment variables are set. Otherwise use the default local addresses.
    #   (The default addresses are typically used in demos.)
    zmq_control = args.zmq_control or os.environ.get("QSERVER_ZMQ_CONTROL_ADDRESS", None)
    zmq_publish = args.zmq_publish or os.environ.get("QSERVER_ZMQ_PUBLISH_ADDRESS", None)
    SETTINGS.zmq_re_manager_control_addr = zmq_control
    SETTINGS.zmq_re_manager_publish_addr = zmq_publish

    with gui_qt("BlueSky Queue Monitor"):
        viewer = Viewer()  # noqa: 401


if __name__ == "__main__":
    main()
