import argparse
import os

from bluesky_widgets.qt import gui_qt

from .viewer import Viewer
from .settings import SETTINGS


def main(argv=None):
    parser = argparse.ArgumentParser(description="BlueSky Queue Monitor")
    parser.add_argument(
        "--zmq-control-addr",
        help="Address of control socket of RE Manager. If the address "
        "is passed as a CLI parameter, it overrides the address specified with "
        "QSERVER_ZMQ_CONTROL_ADDRESS environment variable. Default address is "
        "used if the parameter or the environment variable are not specified.",
    )
    parser.add_argument(
        "--zmq-control",
        help="The parameter is deprecated and will be removed. Use --zmq-control-addr instead.",
    )
    parser.add_argument(
        "--zmq-info-addr",
        help="Address of PUB-SUB socket of RE Manager. If the address "
        "is passed as a CLI parameter, it overrides the address specified with "
        "QSERVER_ZMQ_INFO_ADDRESS environment variable. Default address is "
        "used if the parameter or the environment variable are not specified.",
    )
    parser.add_argument(
        "--zmq-publish",
        help="The parameter is deprecated and will be removed. Use --zmq-info-addr instead.",
    )
    args = parser.parse_args(argv)

    # The priority is first to check if an address is passed as a parameter and then
    #   check if the environment variables are set. Otherwise use the default local addresses.
    #   (The default addresses are typically used in demos.)
    zmq_control_addr = args.zmq_control or os.environ.get("QSERVER_ZMQ_CONTROL_ADDRESS", None)
    zmq_info_addr = args.zmq_publish or os.environ.get("QSERVER_ZMQ_PUBLISH_ADDRESS", None)
    if "QSERVER_ZMQ_PUBLISH_ADDRESS" in os.environ:
        print("WARNING: Environment variable QSERVER_ZMQ_PUBLISH_ADDRESS is deprecated and will be removed.")
        print("    Use QSERVER_ZMQ_CONTROL_ADDRESS environment variable instead.")
    zmq_info_addr = args.zmq_publish or os.environ.get("QSERVER_ZMQ_PUBLISH_ADDRESS", None)
    SETTINGS.zmq_re_manager_control_addr = zmq_control_addr
    SETTINGS.zmq_re_manager_info_addr = zmq_info_addr

    with gui_qt("BlueSky Queue Monitor"):
        viewer = Viewer()  # noqa: 401


if __name__ == "__main__":
    main()
