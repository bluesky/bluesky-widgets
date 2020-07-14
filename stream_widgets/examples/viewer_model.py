from stream_widgets.components.search.searches import SearchList
from stream_widgets.components.runs import RunList
from stream_widgets.examples.utils.add_search_mixin import AddSearchMixin


class ViewerModel(AddSearchMixin):
    """
    Compose various models into one object to provide a nice user API.
    """
    def __init__(self, title):
        self.title = title
        self.searches = SearchList()
        self.runs = RunList()
        super().__init__()
