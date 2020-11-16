"""
As of this writing, this is not used but may be useful later.
"""
from .event import EmitterGroup, Event


class EventedDict:
    "This is an incomplete implementation of the MutableMapping interface."
    def __init__(self, *args, **kwargs):
        self.__internal_dict = dict(*args, **kwargs)
        self.events = EmitterGroup(
            source=self,
            auto_connect=True,
            added=Event,
            removed=Event,
        )

    def __getitem__(self, key):
        return self.__internal_dict[key]

    def __delitem__(self, key):
        obj = self.__internal_dict.pop(key)
        self.events.removed(item=obj, key=key)

    def __setitem__(self, key, obj):
        old = self.__internal_dict[key]
        self.__internal_dict[key] = obj
        self.events.removed(item=old, key=key)
        self.events.added(item=obj, key=key)

    def __len__(self):
        return len(self.__internal_dict)

    def update(self, d):
        added = []
        removed = []
        for key in d:
            if key in self.__internal_dict:
                if self.__internal_dict[key] is not obj:
                    removed.append((key, obj))
            else:
                added.append((key, obj))
        self.__internal_dict.update(d)
        for key, obj in addded:
            self.events.added(item=obj, key=key)
        for key, obj in removed:
            self.events.removed(item=obj, key=key)

    def pop(self, key):
        obj = self.__internal_dict.pop(key)
        self.events.removed(item=obj, key=key)
        return obj

    def clear(self):
        for key, obj in self.__internal_dict.items():
            del self.__internal_dict[key]
            self.events.removed(item=obj, key=key)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.__internal_dict})"
