from collections import abc

from qtpy import QtCore
from qtpy.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    Qt,
)
from qtpy.QtWidgets import QAbstractItemView, QTreeView

from databroker.core import BlueskyEventStream


class RunTree:
    """Lazily populate the tree as data is requested."""

    def __init__(self, bs_run):
        self.run = bs_run
        self.children = []

        uid = RunNode(self.run, "uid", self.run.metadata["start"]["uid"], None, self)
        start = RunNode(self.run, "start", "dict", self.run.metadata["start"], self)
        start.num_children = len(self.run.metadata["start"])
        stop = RunNode(self.run, "stop", "dict", self.run.metadata["stop"], self)
        stop.num_children = len(self.run.metadata["stop"])
        streams = RunNode(self.run, "streams", f"({len(self.run)})", None, self)
        streams.num_children = len(self.run)
        self.children = [uid, start, stop, streams]

    def count(self):
        return len(self.children)

    def child(self, row):
        if row >= 0 and row < len(self.children):
            return self.children[row]
        return None


class RunNode(object):
    def __init__(self, run, key, value, data=None, parent=None):
        self.run = run
        self.parent = parent
        self.key = key
        self.value = value
        self.data = data
        self.children = []
        self.num_children = 0

    def child_count(self):
        return self.num_children

    def child(self, row):
        """Lazily fill these in when we can..."""
        if len(self.children) == 0 and self.num_children != len(self.children):
            self.fill_children()

        if row >= 0 and row < len(self.children):
            return self.children[row]

    def child_number(self):
        return self.parent.children.index(self)

    def fill_streams(self):
        """Fill the streams in."""
        for stream in self.run:
            num_events = self.run.metadata["stop"]["num_events"]
            if stream in num_events:
                n = num_events[stream]
                if n == 0:
                    value = "0 events"
                if n == 1:
                    value = "1 event"
                else:
                    value = f"{str(n)} events"
            else:
                value = "null"
            child = RunNode(self.run, stream, value, self.run[stream], self)
            # Establish how many child nodes there will be.
            stream_keys = self.run[stream].metadata["descriptors"][0]["data_keys"]
            child.num_children = len(stream_keys) + 2

            self.children.append(child)

    def fill_stream(self, stream):
        # For now just display the keys in the stream.
        node = RunNode(self.run, "metadata", "dict", self.data.metadata, self)
        node.num_children = len(self.data.metadata) - 1
        self.children.append(node)
        descriptors = self.data.metadata["descriptors"]
        if len(descriptors) == 1:
            node = RunNode(self.run, "descriptors (1)", "", descriptors[0], self)
            node.num_children = len(descriptors[0])
        else:
            node = RunNode(self.run, f"descriptors ({len(descriptors)})", descriptors, self)
            node.num_children = len(descriptors)

        self.children.append(node)
        stream_keys = self.data.metadata["descriptors"][0]["data_keys"]
        for key in stream_keys:
            value = f"{stream_keys[key]['dtype']} {stream_keys[key]['shape']}"
            child = RunNode(self.run, key, value, None, self)
            self.children.append(child)

    def fill_dict(self, data):
        for key in self.data:
            if isinstance(self.data[key], abc.Mapping):
                value = ""
            elif key == "descriptors":
                # This is "lifted up" and so skipping so as not to repeat.
                continue
            elif isinstance(self.data[key], abc.Iterable):
                value = str(self.data[key])
            else:
                value = self.data[key]
            child = RunNode(self.run, key, value, self.data[key], self)
            if isinstance(self.data[key], abc.Mapping):
                child.num_children = len(self.data[key])
            self.children.append(child)

    def fill_children(self):
        """Handle special ones like streams first."""
        if self.key == "streams":
            self.fill_streams()
        elif self.data and isinstance(self.data, BlueskyEventStream):
            self.fill_stream(self.data)
        elif self.data and isinstance(self.data, abc.Mapping):
            self.fill_dict(self.data)


class TreeViewModel(QAbstractItemModel):
    """
    Qt model connecting our run model to Qt's model-view machinery
    """

    def __init__(self, bs_run, parent=None):
        super(TreeViewModel, self).__init__(parent)

        self._catalog = bs_run
        if bs_run is not None:
            self._run_tree = RunTree(bs_run)
        else:
            self._run_tree = None

    def setRun(self, bs_run):
        self.beginResetModel()
        self._catalog = bs_run
        if bs_run is not None:
            self._run_tree = RunTree(bs_run)
        else:
            self._run_tree = None
        self.endResetModel()

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self._run_tree
        else:
            parentItem = parent.internalPointer()

        child = parentItem.child(row)
        if child:
            return self.createIndex(row, column, child)
        else:
            print("index not created ", row, " -> ", child, parent.key)

        return QModelIndex()

    def parent(self, index):
        """Return the parent."""
        if not index.isValid:
            return QModelIndex()
        item = index.internalPointer()
        if not item:
            return QModelIndex()

        parent = item.parent
        if parent == self._run_tree:
            return QModelIndex()
        else:
            return self.createIndex(parent.child_number(), 0, parent)

        return QModelIndex()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return parent.internalPointer().child_count()
        elif not parent.isValid() and self._run_tree is not None:
            return self._run_tree.count()
        return 0

    def columnCount(self, parent=None):
        return 2

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return super().headerData(section, orientation, role)
        if orientation == Qt.Horizontal and section < self.columnCount():
            if section == 0:
                return str("Key")
            else:
                return str("Value")
            return str("test")
        elif orientation == Qt.Vertical and section < self.rowCount():
            return section

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid() and role == Qt.DisplayRole:
            if index.column() == 0:
                return index.internalPointer().key
            else:
                return index.internalPointer().value
        elif not index.isValid():
            return "root"
        return QtCore.QVariant()


class QtTreeView(QTreeView):
    """
    Tree view showing a run
    """

    def __init__(self, model, parent=None):
        super(QtTreeView, self).__init__(parent)
        self.model = model

        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(True)

        # Initialize model.
        self._abstract_item_model = TreeViewModel(model.run)
        self.setModel(self._abstract_item_model)

        # Listen for future changes to model.
        self.model.events.run.connect(self.on_run_changed)

    def on_run_changed(self, event):
        self._abstract_item_model = TreeViewModel(event.run)
        self.setModel(self._abstract_item_model)
