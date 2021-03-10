from qtpy.QtWidgets import QListWidget


class QtPlanQueue(QListWidget):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

        for item in self.model:
            self.addItem(repr(item))

        self.model.events.added.connect(self._on_item_added)
        self.model.events.removed.connect(self._on_item_removed)

    def _on_item_added(self, event):
        self.insertItem(event.index, repr(event.item))

    def _on_item_removed(self, event):
        widget = self.item(event.index)
        self.removeItemWidget(widget)
