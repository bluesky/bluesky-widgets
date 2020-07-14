"""
This is a simplified version of napari.utils.list._model until I understand why
I would need the more complicated Typed and MultiIndexed aspects.
"""
from .event import EmitterGroup, Event


class ListModel:
    def __init__(self, iterable=None):
        self.__internal_list = list(iterable or [])
        self.events = EmitterGroup(
            source=self,
            auto_connect=True,
            added=Event,
            removed=Event,
            changed=Event,
        )

    def __getitem__(self, index):
        return self.__internal_list[index]

    def __delitem__(self, index):
        obj = self.__internal_list.pop(index)
        self.removed(item=obj, index=index)

    def __setitem__(self, index, obj):
        self.__internal_list[index] = obj
        self.events.changed(item=obj, index=index)

    def __len__(self):
        return len(self.__internal_list)

    def insert(self, index, obj):
        self.__internal_list.insert(index, obj)
        self.events.added(item=obj, index=index)

    def append(self, obj):
        self.__internal_list.append(obj)
        self.events.added(item=obj, index=len(self) - 1)

    def pop(self, index=-1):
        obj = self.__internal_list.pop(index)
        self.events.removed(item=obj, index=index)
        return obj

    def clear(self):
        while True:
            try:
                obj = self.__internal_list.pop()
            except IndexError:
                break
            self.events.removed(item=obj, index=-1)
