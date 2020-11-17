from collections import namedtuple
import uuid as uuid_module


def define_spec(typename, field_names, *, rename=False, defaults=None, module=None):
    """
    This is a wrapper around namedtuple that adds a uuid field with a default value.

    This allows it to be hashable even when the contents are mutable, by making
    the uuid the "identity" of the object.
    """
    if isinstance(field_names, str):
        # namedtuple support field_names as space- or comma-separated string
        field_names = field_names.replace(",", " ").split()
    if "uuid" in field_names:
        raise ValueError(
            "The field name 'uuid' has special significance in specs "
            "and is reserved."
        )
    field_names.append("uuid")

    # Construct a standard namedtuple.
    base_class = namedtuple(
        typename, field_names, rename=rename, defaults=defaults, module=module
    )

    # And override it to add an auto-generated uuid.
    class result(base_class):
        __slots__ = ()

        def __new__(cls, *args, **kwargs):
            if "uuid" not in kwargs and len(args) < len(field_names):
                kwargs.update({"uuid": uuid_module.uuid4()})
            return super().__new__(cls, *args, **kwargs)

        def __hash__(self):
            return self.uuid.int

        def __eq__(self, other):

            # Compare the contents as usual but omit the uuid.
            return isinstance(other, type(self)) and self[:-1] == other[:-1]

    result.__name__ = typename
    result.__qualname__ = typename

    # This makes pickling work, just as it is done in namedtuple itself.

    # For pickling to work, the __module__ variable needs to be set to the frame
    # where the named tuple is created.  Bypass this step in environments where
    # sys._getframe is not defined (Jython for example) or sys._getframe is not
    # defined for arguments greater than 0 (IronPython), or where the user has
    # specified a particular module.
    if module is None:
        try:
            import sys

            module = sys._getframe(1).f_globals.get("__name__", "__main__")
        except (AttributeError, ValueError):
            pass
    if module is not None:
        result.__module__ = module

    return result
