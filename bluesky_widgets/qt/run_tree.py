from qtpy import QtCore
from qtpy.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    Qt,
)
from qtpy.QtWidgets import QAbstractItemView, QTreeView

from databroker.core import BlueskyEventStream


class RunTree(object):
    """Lazily populate the tree as data is requested. """
    def __init__(self, run):
        self.run = run
        self.children = []

        uid = RunNode(self.run, 'uid', self.run.metadata['start']['uid'], None, self)
        start = RunNode(self.run, 'start', 'dict', self.run.metadata['start'], self)
        start.num_children = len(self.run.metadata['start'])
        stop = RunNode(self.run, 'stop', 'dict', self.run.metadata['stop'], self)
        stop.num_children = len(self.run.metadata['stop'])
        streams = RunNode(self.run, 'streams', 'events (' + str(len(self.run)) + ')', None, self)
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

    def fill_children(self):
        """Handle special ones like streams first."""
        if self.key == 'streams':
            for stream in self.run:
                num_events = self.run.metadata['stop']['num_events']
                if stream in num_events:
                    n = num_events[stream]
                    if n == 0:
                        value = '0 events'
                    if n == 1:
                        value = '1 event'
                    else:
                        value = str(n) + ' events'
                else:
                    value = 'null'
                child = RunNode(self.run, stream, value, self.run[stream], self)
                # Establish how many child nodes there will be.
                child.num_children = len(self.run[stream].read().keys())
                self.children.append(child)
        elif self.data and isinstance(self.data, BlueskyEventStream):
            # For now just display the keys in the stream.
            node = RunNode(self.run, 'metadata', 'dict', self.data.metadata, self)
            node.num_children = len(self.data.metadata)
            self.children.append(node)
            for key in self.data.read().keys():
                child = RunNode(self.run, key, '', None, self)
                self.children.append(child)
        elif self.data and isinstance(self.data, dict):
            for key in self.data:
                if isinstance(self.data[key], dict):
                    value = ''
                elif isinstance(self.data[key], list):
                    value = str(self.data[key])
                else:
                    value = self.data[key]
                child = RunNode(self.run, key, value, self.data[key], self)
                if isinstance(self.data[key], dict):
                    child.num_children = len(self.data[key])
                self.children.append(child)


class TreeViewModel(QAbstractItemModel):
    """
    Qt model connecting our run model to Qt's model-view machinery
    """

    def __init__(self, bs_run, parent=None):
        super(TreeViewModel, self).__init__(parent)

        self._catalog = bs_run
        self._run_tree = RunTree(bs_run)

        # State related to dynamically adding rows
        self._current_num_rows = len(self._catalog)
        self._catalog_length = len(self._catalog)

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
        """ Return the parent."""
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
        elif not parent.isValid():
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

    def __init__(self, parent=None, bs_run=None):
        super(QtTreeView, self).__init__(parent)
        self._run = bs_run

        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(True)
        self._abstract_item_model = TreeViewModel(bs_run)
        self.setModel(self._abstract_item_model)
