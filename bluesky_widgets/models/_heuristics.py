"""
This module contains utility functions used by the built-in auto-plotters.
The module is private because the interfaces may change in the future.
Use the auto-plotters in bluesky_widgets.models.auto_plot_builders to use this
functionality.
"""

def hinted_fields(descriptor):
    # Figure out which columns to put in the table.
    obj_names = list(descriptor["object_keys"])
    # We will see if these objects hint at whether
    # a subset of their data keys ('fields') are interesting. If they
    # did, we'll use those. If these didn't, we know that the RunEngine
    # *always* records their complete list of fields, so we can use
    # them all unselectively.
    columns = []
    for obj_name in obj_names:
        try:
            fields = descriptor.get("hints", {}).get(obj_name, {})["fields"]
        except KeyError:
            fields = descriptor["object_keys"][obj_name]
        columns.extend(fields)
    return columns
