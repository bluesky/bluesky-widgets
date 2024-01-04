from bluesky_live.event import *  # noqa: F401,F403
import warnings

warnings.warn(
    "The contents of bluesky_widgets.utils.event has "
    "been moved to bluesky_live.event, please import from there."
    "This module may be removed in the future",
    stacklevel=2,
)
