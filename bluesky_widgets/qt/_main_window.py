"""
Custom Qt widgets that serve as native objects that the public-facing elements
wrap.
"""
import time

from qtpy.QtWidgets import (  # noqa: E402
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QLabel,
    QStatusBar,
    QFileDialog,
)
from qtpy.QtCore import Qt  # noqa: E402

from ._event_loop import get_our_app_name
from .threading import wait_for_workers_to_quit


class Window:
    """Application window that contains the menu bar and viewer.

    Parameters
    ----------
    qt_widget : QtViewer
        Contained viewer widget.

    Attributes
    ----------
    file_menu : qtpy.QtWidgets.QMenu
        File menu.
    help_menu : qtpy.QtWidgets.QMenu
        Help menu.
    main_menu : qtpy.QtWidgets.QMainWindow.menuBar
        Main menubar.
    qt_widget : QtViewer
        Contained viewer widget.
    view_menu : qtpy.QtWidgets.QMenu
        View menu.
    window_menu : qtpy.QtWidgets.QMenu
        Window menu.
    """

    def __init__(self, qt_widget, *, show):

        self.qt_widget = qt_widget

        self._qt_window = QMainWindow()
        self._qt_window.setAttribute(Qt.WA_DeleteOnClose)
        self._qt_window.setUnifiedTitleAndToolBarOnMac(True)
        self._qt_center = QWidget(self._qt_window)

        self._qt_window.setCentralWidget(self._qt_center)
        if hasattr(self.qt_widget.model, "title"):
            self._qt_window.setWindowTitle(self.qt_widget.model.title)
        self._qt_center.setLayout(QHBoxLayout())
        self._status_bar = QStatusBar()
        self._qt_window.setStatusBar(self._status_bar)

        self._status_bar.showMessage("Ready")
        self._help = QLabel("")
        self._status_bar.addPermanentWidget(self._help)

        self._qt_center.layout().addWidget(self.qt_widget)
        self._qt_center.layout().setContentsMargins(4, 0, 4, 0)

        # self._add_viewer_dock_widget(self.qt_widget.dockConsole)
        # self._add_viewer_dock_widget(self.qt_widget.dockLayerControls)
        # self._add_viewer_dock_widget(self.qt_widget.dockLayerList)

        # self.qt_widget.viewer.events.status.connect(self._status_changed)
        # self.qt_widget.viewer.events.help.connect(self._help_changed)
        # self.qt_widget.viewer.events.title.connect(self._title_changed)
        # self.qt_widget.viewer.events.palette.connect(self._update_palette)

        if show:
            self.show()

    def resize(self, width, height):
        """Resize the window.

        Parameters
        ----------
        width : int
            Width in logical pixels.
        height : int
            Height in logical pixels.
        """
        self._qt_window.resize(width, height)

    def show(self):
        """Resize, show, and bring forward the window."""
        self._qt_window.resize(self._qt_window.layout().sizeHint())
        self._qt_window.show()

        # We want to call Window._qt_window.raise_() in every case *except*
        # when instantiating a viewer within a gui_qt() context for the
        # _first_ time within the Qt app's lifecycle.
        #
        # `app_name` will be ours iff the application was instantiated in
        # gui_qt(). isActiveWindow() will be True if it is the second time a
        # _qt_window has been created. See #732
        app_name = QApplication.instance().applicationName()
        if app_name != get_our_app_name() or self._qt_window.isActiveWindow():
            self._qt_window.raise_()  # for macOS
            self._qt_window.activateWindow()  # for Windows

    def _status_changed(self, event):
        """Update status bar.

        Parameters
        ----------
        event : qtpy.QtCore.QEvent
            Event from the Qt context.
        """
        self._status_bar.showMessage(event.text)

    def _title_changed(self, event):
        """Update window title.

        Parameters
        ----------
        event : qtpy.QtCore.QEvent
            Event from the Qt context.
        """
        self._qt_window.setWindowTitle(event.text)

    def _help_changed(self, event):
        """Update help message on status bar.

        Parameters
        ----------
        event : qtpy.QtCore.QEvent
            Event from the Qt context.
        """
        self._help.setText(event.text)

    def _screenshot_dialog(self):
        """Save screenshot of current display with viewer, default .png"""
        filename, _ = QFileDialog.getSaveFileName(
            parent=self.qt_widget,
            caption="Save screenshot with viewer",
            directory=self.qt_widget._last_visited_dir,  # home dir by default
            filter="Image files (*.png *.bmp *.gif *.tif *.tiff)",  # first one used by default
            # jpg and jpeg not included as they don't support an alpha channel
        )
        if (filename != "") and (filename is not None):
            # double check that an appropriate extension has been added as the
            # filter option does not always add an extension on linux and windows
            # see https://bugreports.qt.io/browse/QTBUG-27186
            image_extensions = (".bmp", ".gif", ".png", ".tif", ".tiff")
            if not filename.endswith(image_extensions):
                filename = filename + ".png"
            self.screenshot(path=filename)

    def screenshot(self, path=None):
        """Take currently displayed viewer and convert to an image array.

        Parameters
        ----------
        path : str
            Filename for saving screenshot image.

        Returns
        -------
        image : array
            Numpy array of type ubyte and shape (h, w, 4). Index [0, 0] is the
            upper-left corner of the rendered region.
        """
        img = self._qt_window.grab().toImage()
        if path is not None:
            from skimage.io import imsave
            from .utils import QImg2array  # noqa: E402

            imsave(path, QImg2array(img))
        return QImg2array(img)

    def close(self):
        """Close the viewer window and cleanup sub-widgets."""
        # on some versions of Darwin, exiting while fullscreen seems to tickle
        # some bug deep in NSWindow.  This forces the fullscreen keybinding
        # test to complete its draw cycle, then pop back out of fullscreen.
        if self._qt_window.isFullScreen():
            self._qt_window.showNormal()
            for i in range(8):
                time.sleep(0.1)
                QApplication.processEvents()
        self.qt_widget.close()
        self._qt_window.close()
        wait_for_workers_to_quit()
        del self._qt_window
