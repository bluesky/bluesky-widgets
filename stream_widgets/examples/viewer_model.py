from stream_widgets.components.search.searches import SearchList
from stream_widgets.examples.utils.add_search_mixin import AddSearchMixin


class ViewerModel(AddSearchMixin):
    """
    Compose various models (search input, search results, ...) into one object.
    """
    def __init__(self, title):
        self.title = title
        self.searches = SearchList()
        super().__init__()
