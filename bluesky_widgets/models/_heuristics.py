"""
This module contains utility functions used by the built-in auto-plotters.
The module is private because the interfaces may change in the future.
Use the auto-plotters in bluesky_widgets.models.auto_plot_builders to use this
functionality.
"""


def hinted_fields(descriptor):
    "Which columns are the most important ones to show and visualize?"
    columns = []
    if descriptor["object_keys"]:
        # We will see if these objects hint at whether
        # a subset of their data keys ('fields') are interesting. If they
        # did, we'll use those. If these didn't, we know that the RunEngine
        # *always* records their complete list of fields, so we can use
        # them all unselectively.
        for obj_name, all_fields in descriptor["object_keys"].items():
            try:
                fields = descriptor.get("hints", {}).get(obj_name, {})["fields"]
            except KeyError:
                fields = all_fields
            columns.extend(fields)
    else:
        # There are no object_keys. This came from something other than the
        # RunEngine. Just use all the columns.
        columns.extend(descriptor["data_keys"])
    return columns
