import collections.abc
from .event import Event, EmitterGroup


class DictView(collections.abc.Mapping):
    def __init__(self, d):
        self._internal_dict = d

    def __repr__(self):
        return f"{self.__class__.__name__}({self._internal_dict!r})"

    def __getitem__(self, key):
        return self._internal_dict[key]

    def __iter__(self):
        yield from self._internal_dict

    def __len__(self):
        return len(self._internal_dict)

    def __setitem__(self, key, value):
        raise TypeError("Setting items in this dict is not allowed. ")

    def __delitem__(self, key):
        raise TypeError("Deleting items from this dict is not allowed. ")


class UpdateOnlyDict(DictView):
    """
    A dict that only allows mutation through update() and is observable.

    This matches the semantics of matplotlib's Artist.set and is used in that
    context.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = EmitterGroup(source=self, updated=Event)

    def update(self, *args, **kwargs):
        self._internal_dict.update(*args, **kwargs)
        self.events.updated(update=dict(*args, **kwargs))
