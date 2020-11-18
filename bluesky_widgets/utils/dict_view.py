import collections.abc


class DictView(collections.abc.Mapping):
    def __init__(self, d):
        self.__internal_dict = d

    def __repr__(self):
        return f"({self.__internal_dict!r})"

    def __getitem__(self, key):
        return self.__internal_dict[key]

    def __iter__(self):
        yield from self.__internal_dict

    def __len__(self):
        return len(self.__internal_dict)

    def __setitem__(self, key, value):
        raise TypeError(
            "Setting items in this dict is not allowed. "
            "Instead, replace the whole dict."
        )

    def __delitem__(self, key):
        raise TypeError(
            "Deleting items from this dict is not allowed. "
            "Instead, replace the whole dict."
        )
