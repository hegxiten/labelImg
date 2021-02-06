#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import codecs
import distutils.spawn
import os.path
import platform
import re
import sys
import subprocess

from functools import partial
from collections import defaultdict

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip
        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.resources import *
from libs.constants import *
from libs.utils import *
from libs.settings import Settings
from libs.stringBundle import StringBundle
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.attributeDialog import AttributeDialog
from libs.attributeFile import AttributeFile, AttributeFileError, AttributeFileFormat, ATTRIBUTE_KEYS
from libs.toolBar import ToolBar
from libs.attributeJSONIO import AttributeJSONWriter, AttributeJSONReader
from libs.attributeJSONIO import JSON_EXT
from libs.ustr import ustr

__appname__ = 'David Corbitt Photo Organizer'


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, defaultFilename=None, defaultSaveDir=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        # Initiate image and attribute file objects
        self.imageData = None
        self.attributeFile = None
        self.updatedAttributeDict = {}
        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings

        # Load string bundle for i18n
        self.stringBundle = StringBundle.getBundle()
        getStr = lambda strId: self.stringBundle.getString(strId)

        # Save as json
        self.defaultSaveDir = defaultSaveDir
        self.attributeFileFormat = settings.get(SETTING_ATTRIBUTE_FILE_FORMAT, AttributeFileFormat.JSON)
        # For loading all image under a directory
        self.mImgFileList = []
        self.dirname = None
        self.globalLabelList = []
        self.lastOpenDir = None

        # Whether we need to save or not.
        self.dirty = False

        self._noSelectionSlot = False
        self._beginner = True
        self.screencastViewer = self.getAvailableScreencastViewer()
        self.screencast = "https://youtu.be/p0nR2YsCY_U"

        # Main widgets and related state.
        self.attributeDialog = AttributeDialog(parent=self)
        self.attributeDialog.setGeometry(
            QStyle.alignedRect(Qt.LeftToRight, Qt.AlignCenter, self.attributeDialog.size(), qApp.desktop().availableGeometry())
        )
        self.prevLabelText = ''

        listLayout = QVBoxLayout()
        listLayout.setContentsMargins(0, 0, 0, 0)

        # Create and add a table widget for showing attribute key-values
        self.attributeTableWidget = QTableWidget()
        tableWidgetContainer = QWidget()
        tableWidgetContainer.setLayout(listLayout)
        self.attributeTableWidget.itemDoubleClicked.connect(self.editAttribute)
        self.attributeTableWidget.itemChanged.connect(self.attributeItemChanged)
        self.attributeTableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        listLayout.addWidget(self.attributeTableWidget)

        self.photoAttributeDock = QDockWidget(getStr('photoAttributeDockText'), self)
        self.photoAttributeDock.setObjectName(getStr('attributes'))
        self.photoAttributeDock.setWidget(tableWidgetContainer)

        self.fileListWidget = QListWidget()
        self.fileListWidget.itemDoubleClicked.connect(self.fileitemDoubleClicked)
        fileListLayout = QVBoxLayout()
        fileListLayout.setContentsMargins(0, 0, 0, 0)
        fileListLayout.addWidget(self.fileListWidget)
        fileListContainer = QWidget()
        fileListContainer.setLayout(fileListLayout)

        self.fileDock = QDockWidget(getStr('fileList'), self)
        self.fileDock.setObjectName(getStr('files'))
        self.fileDock.setWidget(fileListContainer)

        self.zoomWidget = ZoomWidget()

        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoomRequest)
        self.canvas.setDrawingShapeToSquare(settings.get(SETTING_DRAW_SQUARE, False))

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }
        self.scrollArea = scroll
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.photoAttributeDock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.fileDock)

        self.dockFeatures = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.fileDock.setFeatures(self.fileDock.features() ^ self.dockFeatures)
        self.photoAttributeDock.setFeatures(self.photoAttributeDock.features() ^ self.dockFeatures)

        # Init actions and corresponding callback functions, keyboard shortcuts
        action = partial(newAction, self)
        quit = action(getStr('quit'), self.close,
                      'Ctrl+Q', 'quit', getStr('quitApp'))

        open = action(getStr('openFile'), self.openFile,
                      'Ctrl+O', 'open', getStr('openFileDetail'))

        opendir = action(getStr('openDir'), self.openDirDialog,
                         'Ctrl+u', 'open', getStr('openDir'))

        openNextImg = action(getStr('nextImg'), self.openNextImg,
                             'd', 'next', getStr('nextImgDetail'))

        openPrevImg = action(getStr('prevImg'), self.openPrevImg,
                             'a', 'prev', getStr('prevImgDetail'))

        save = action(getStr('save'), self.saveFile,
                      'Ctrl+S', 'save', getStr('saveDetail'), enabled=False)

        close = action(getStr('closeCur'), self.closeFile, 'Ctrl+W', 'close', getStr('closeCurDetail'))

        resetAll = action(getStr('resetAll'), self.resetAll, None, 'resetall', getStr('resetAllDetail'))

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (fmtShortcut("Ctrl+[-+]"),
                                             fmtShortcut("Ctrl+Wheel")))
        self.zoomWidget.setEnabled(False)

        zoomIn = action(getStr('zoomin'), partial(self.addZoom, 10),
                        'Ctrl++', 'zoom-in', getStr('zoominDetail'), enabled=False)
        zoomOut = action(getStr('zoomout'), partial(self.addZoom, -10),
                         'Ctrl+-', 'zoom-out', getStr('zoomoutDetail'), enabled=False)
        zoomOrg = action(getStr('originalsize'), partial(self.setZoom, 100),
                         'Ctrl+=', 'zoom', getStr('originalsizeDetail'), enabled=False)
        fitWindow = action(getStr('fitWin'), self.setFitWindow,
                           'Ctrl+F', 'fit-window', getStr('fitWinDetail'),
                           checkable=True, enabled=False)
        fitWidth = action(getStr('fitWidth'), self.setFitWidth,
                          'Ctrl+Shift+F', 'fit-width', getStr('fitWidthDetail'),
                          checkable=True, enabled=False)
        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut,
                       zoomOrg, fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        labels = self.photoAttributeDock.toggleViewAction()
        labels.setText(getStr('showHide'))
        labels.setShortcut('Ctrl+Shift+L')

        # Store actions for further handling.
        self.actions = struct(save=save, open=open, close=close, resetAll = resetAll,
                              zoom=zoom, zoomIn=zoomIn, zoomOut=zoomOut, zoomOrg=zoomOrg,
                              fitWindow=fitWindow, fitWidth=fitWidth,
                              zoomActions=zoomActions,
                              fileMenuActions=(
                                  open, opendir, save, close, resetAll, quit),
                              onImgLoadedActive=(close,),
                              )

        self.menus = struct(
            file=self.menu(getStr('menu_file')),
            view=self.menu(getStr('menu_view')),
            recentFiles=QMenu(getStr('menu_openRecent')))

        # Auto saving : Enable auto saving if pressing next
        self.autoSaving = QAction(getStr('autoSaveMode'), self)
        self.autoSaving.setCheckable(True)
        self.autoSaving.setChecked(settings.get(SETTING_AUTO_SAVE, False))
        # Sync single class mode from PR#106
        self.singleClassMode = QAction(getStr('singleClsMode'), self)
        self.singleClassMode.setShortcut("Ctrl+Shift+S")
        self.singleClassMode.setCheckable(True)
        self.singleClassMode.setChecked(settings.get(SETTING_SINGLE_CLASS, False))

        addActions(self.menus.file, (open, opendir, self.menus.recentFiles, save, close, resetAll, quit))
        addActions(self.menus.view, (self.autoSaving, None, zoomIn, zoomOut, zoomOrg, None, fitWindow, fitWidth))

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        self.toolbarActions = (
            open, opendir, openNextImg, openPrevImg, save, close, None,
            zoomIn, zoom, zoomOut, fitWindow, fitWidth)

        self.tools = self.toolbar('Tools')
        self.tools.clear()
        addActions(self.tools, self.toolbarActions)

        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.imgFilePath = ustr(defaultFilename)
        self.lastOpenDir = None
        self.recentFiles = []
        self.maxRecent = 7
        self.zoom_level = 100
        self.fit_window = False

        ## Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recentFileQStringList = settings.get(SETTING_RECENT_FILES)
                self.recentFiles = [ustr(i) for i in recentFileQStringList]
            else:
                self.recentFiles = recentFileQStringList = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(900, 500))
        position = QPoint(0, 0)
        saved_position = settings.get(SETTING_WIN_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break
        self.resize(size)
        self.move(position)
        saveDir = ustr(settings.get(SETTING_SAVE_DIR, None))
        self.lastOpenDir = ustr(settings.get(SETTING_LAST_OPEN_DIR, None))
        if self.defaultSaveDir is None and saveDir is not None and os.path.exists(saveDir):
            self.defaultSaveDir = saveDir
            self.statusBar().showMessage('%s started. Attributes will be saved to %s' %
                                         (__appname__, self.defaultSaveDir))
            self.statusBar().show()

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))

        # Populate the File menu dynamically.
        self.updateFileMenu()

        # Since loading the file may take some time, make sure it runs in the background.
        if self.imgFilePath and os.path.isdir(self.imgFilePath):
            self.queueEvent(partial(self.importDirImages, self.imgFilePath or ""))
        elif self.imgFilePath:
            self.queueEvent(partial(self.loadFile, self.imgFilePath or ""))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        # Display cursor coordinates at the right of status bar
        self.labelCoordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.labelCoordinates)

        # Open Folder if default file
        if self.imgFilePath and os.path.isdir(self.imgFilePath):
            self.openDirDialog(dirpath=self.imgFilePath, silent=True)

    def setDirty(self):
        self.dirty = True
        self.actions.save.setEnabled(True)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)

    def toggleActions(self, value=True):
        """Enable/Disable widgets (clickable or not) which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onImgLoadedActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.attributeTableWidget.clear()
        self.imgFilePath = None
        self.imageData = None
        self.attributeFile = None
        self.canvas.resetState()

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def currentTableItem(self):
        items = self.attributeTableWidget.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filePath):
        if filePath in self.recentFiles:
            self.recentFiles.remove(filePath)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filePath)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    def getAvailableScreencastViewer(self):
        osName = platform.system()

        if osName == 'Windows':
            return ['C:\\Program Files\\Internet Explorer\\iexplore.exe']
        elif osName == 'Linux':
            return ['xdg-open']
        elif osName == 'Darwin':
            return ['open']

    ## Callbacks ##
    def showTutorialDialog(self):
        subprocess.Popen(self.screencastViewer + [self.screencast])

    def showInfoDialog(self):
        from libs.__init__ import __version__
        msg = u'Name:{0} \nApp Version:{1} \n{2} '.format(__appname__, __version__, sys.version_info)
        QMessageBox.information(self, u'Information', msg)

    def createAttribute(self):
        pass

    def toggleDrawMode(self, edit=True):
        self.canvas.setEditing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def updateFileMenu(self):
        currFilePath = self.imgFilePath

        def exists(filename):
            return os.path.exists(filename)
        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f !=
                 currFilePath and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)

    def editAttribute(self):
        if not self.canvas.editing():
            return
        tableCellItem = self.currentTableItem()
        if not tableCellItem:
            return
        originText = tableCellItem.text()
        newText = self.attributeDialog.popUp(tableCellItem.text())
        tableCellItem.setText(newText)
        if newText != originText:
            self.setDirty()

    # Tzutalin 20160906 : Add file list and photoAttributeDock to move faster
    def fileitemDoubleClicked(self, item=None):
        currIndex = self.mImgFileList.index(ustr(item.text()))
        if currIndex < len(self.mImgFileList):
            filename = self.mImgFileList[currIndex]
            if filename:
                self.loadFile(filename)

    # React to canvas signals.
    def shapeSelectionChanged(self, selected=False):
        if self._noSelectionSlot:
            self._noSelectionSlot = False
        else:
            shape = self.canvas.selectedShape
            if shape:
                self.shapesToLabelItems[shape].setSelected(True)
            else:
                self.labelList.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.edit.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)


    def addAttribute(self, k, v):
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)

    def loadAttributes(self, attributeDict):
        self.attributeDict = attributeDict
        rowCount = len(ATTRIBUTE_KEYS)
        self.attributeTableWidget.setRowCount(rowCount)
        self.attributeTableWidget.setColumnCount(2)
        for i in range(rowCount):
            key = ATTRIBUTE_KEYS[i]
            value = attributeDict.get(key, "")
            keyitem, valueitem = QTableWidgetItem(key), QTableWidgetItem(value)
            keyitem.setFlags(keyitem.flags() ^ Qt.ItemIsSelectable ^ Qt.ItemIsEditable)
            if key == "image":
                valueitem.setFlags(valueitem.flags() ^ Qt.ItemIsSelectable ^ Qt.ItemIsEditable)
            self.attributeTableWidget.setItem(i, 0, keyitem)
            self.attributeTableWidget.setItem(i, 1, valueitem)
        self.updatedAttributeDict = {}


    def updateComboBox(self):
        # Get the unique labels and add them to the Combobox.
        itemsTextList = [str(self.labelList.item(i).text()) for i in range(self.labelList.count())]

        uniqueTextList = list(set(itemsTextList))
        # Add a null row for showing all the labels
        uniqueTextList.append("")
        uniqueTextList.sort()

        self.comboBox.update_items(uniqueTextList)

    def saveAttributes(self, attributeJSONFilePath):
        attributeJSONFilePath = ustr(attributeJSONFilePath)
        try:
            if attributeJSONFilePath[-5:].lower() != ".json":
                attributeJSONFilePath += JSON_EXT
            writer = AttributeJSONWriter(attributeJSONFilePath, self.updatedAttributeDict)
            writer.write()
            return True
        except AttributeFileError as e:
            self.errorMessage(u'Error saving attribute data', u'<b>%s</b>' % e)
            return False

    def attributeItemChanged(self, item):
        row, col = item.row(), item.column()
        key = ATTRIBUTE_KEYS[row]
        self.updatedAttributeDict[key] = item.text()
        if not self.attributeDict.get("image", ""):
            self.updatedAttributeDict["image"] = os.path.basename(self.imgFilePath).split('.')[0]
        self.setDirty()

    # Callback functions:
    def scrollRequest(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)

    def zoomRequest(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scrollBars[Qt.Horizontal]
        v_bar = self.scrollBars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scrollArea.width()
        h = self.scrollArea.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta / (8 * 15)
        scale = 10
        self.addZoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.labelItemsToShapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def loadFile(self, filePath=None):
        """Load the specified file, or the last opened file if None.
        Load the attribute files at the same time. If not exists, create an empty JSON"""
        self.resetState()
        self.canvas.setEnabled(False)
        if filePath is None:
            filePath = self.settings.get(SETTING_FILENAME)

        # Make sure that imgFilePath is a regular python string, rather than QString
        filePath = ustr(filePath)

        # Fix bug: An index error after select a directory when open a new file.
        unicodeFilePath = ustr(filePath)
        unicodeFilePath = os.path.abspath(unicodeFilePath)
        # Tzutalin 20160906 : Add file list and photoAttributeDock to move faster
        # Highlight the file item
        if unicodeFilePath and self.fileListWidget.count() > 0:
            if unicodeFilePath in self.mImgFileList:
                index = self.mImgFileList.index(unicodeFilePath)
                fileWidgetItem = self.fileListWidget.item(index)
                fileWidgetItem.setSelected(True)
            else:
                self.fileListWidget.clear()
                self.mImgFileList.clear()
        if unicodeFilePath and os.path.exists(unicodeFilePath):
            if AttributeFile.isAttributeFile(unicodeFilePath):
                self.errorMessage(u'Error opening file',
                                  u"<p>Make sure <i>%s</i> is a valid image file." % unicodeFilePath)
                self.status("Error reading %s" % unicodeFilePath)
                return False
                # try:
                #     self.attributeFile = AttributeFile(unicodeFilePath)
                # except AttributeFileError as e:
                #     self.errorMessage(u'Error opening file',
                #                       (u"<p><b>%s</b></p>"
                #                        u"<p>Make sure <i>%s</i> is a valid attribute file.")
                #                       % (e, unicodeFilePath))
                #     self.status("Error reading %s" % unicodeFilePath)
                #     return False
            else:
                # Load image:
                # read data first and store for saving into attribute file.
                # not initiating attribute file yet. (intentially set as None)
                reader = QImageReader(unicodeFilePath)
                reader.setAutoTransform(True)
                self.imageData = reader.read()
                self.attributeFile = None
                self.canvas.verified = False

            if isinstance(self.imageData, QImage):
                image = self.imageData
            else:
                image = QImage.fromData(self.imageData)
            if image.isNull():
                self.errorMessage(u'Error opening file',
                                  u"<p>Make sure <i>%s</i> is a valid image file." % unicodeFilePath)
                self.status("Error reading %s" % unicodeFilePath)
                return False
            self.status("Loaded %s" % os.path.basename(unicodeFilePath))
            self.image = image
            self.imgFilePath = unicodeFilePath
            self.canvas.loadPixmap(QPixmap.fromImage(image))
            if not self.attributeFile:
                self.attributeFile = AttributeFile(unicodeFilePath)
                self.loadJsonByFilename(self.attributeFile.jsonFilePath)

            self.setClean()
            self.canvas.setEnabled(True)
            self.adjustScale(initial=True)
            self.paintCanvas()
            self.addRecentFile(self.imgFilePath)
            self.toggleActions(True)
            self.setWindowTitle(__appname__ + ' ' + filePath)
            self.canvas.setFocus(True)
            return True
        return False

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.labelFontSize = int(0.02 * max(self.image.width(), self.image.height()))
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        settings = self.settings
        # If it loads images from dir, don't load it at the beginning
        if self.dirname is None:
            settings[SETTING_FILENAME] = self.imgFilePath if self.imgFilePath else ''
        else:
            settings[SETTING_FILENAME] = ''

        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_RECENT_FILES] = self.recentFiles
        settings[SETTING_ADVANCE_MODE] = not self._beginner
        if self.defaultSaveDir and os.path.exists(self.defaultSaveDir):
            settings[SETTING_SAVE_DIR] = ustr(self.defaultSaveDir)
        else:
            settings[SETTING_SAVE_DIR] = ''

        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            settings[SETTING_LAST_OPEN_DIR] = self.lastOpenDir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ''

        settings[SETTING_AUTO_SAVE] = self.autoSaving.isChecked()
        settings[SETTING_ATTRIBUTE_FILE_FORMAT] = self.attributeFileFormat
        settings.save()

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = ['.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.join(root, file)
                    path = ustr(os.path.abspath(relativePath))
                    images.append(path)
        natural_sort(images, key=lambda x: x.lower())
        return images

    def changeSavedirDialog(self, _value=False):
        self.defaultSaveDir = os.path.dirname(self.imgFilePath)
        return

    def openDirDialog(self, _value=False, dirpath=None, silent=False):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else '.'
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = os.path.dirname(self.imgFilePath) if self.imgFilePath else '.'
        if not silent:
            targetDirPath = ustr(QFileDialog.getExistingDirectory(self,
                                                         '%s - Open Folderectory' % __appname__, defaultOpenDirPath,
                                                         QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        else:
            targetDirPath = ustr(defaultOpenDirPath)
        self.lastOpenDir = targetDirPath
        self.importDirImages(targetDirPath)

    def importDirImages(self, dirpath):
        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.dirname = dirpath
        self.imgFilePath = None
        self.fileListWidget.clear()
        self.mImgFileList = self.scanAllImages(dirpath)
        self.openNextImg()
        for imgPath in self.mImgFileList:
            item = QListWidgetItem(imgPath)
            self.fileListWidget.addItem(item)

    def openPrevImg(self, _value=False):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
            else:
                self.changeSavedirDialog()
                return

        if not self.mayContinue():
            return

        if len(self.mImgFileList) <= 0:
            return

        if self.imgFilePath is None:
            return

        currIndex = self.mImgFileList.index(self.imgFilePath)
        if currIndex - 1 >= 0:
            filename = self.mImgFileList[currIndex - 1]
            if filename:
                self.loadFile(filename)

    def openNextImg(self, _value=False):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
            else:
                self.changeSavedirDialog()
                return

        if not self.mayContinue():
            return

        if len(self.mImgFileList) <= 0:
            return

        filename = None
        if self.imgFilePath is None:
            filename = self.mImgFileList[0]
        else:
            currIndex = self.mImgFileList.index(self.imgFilePath)
            if currIndex + 1 < len(self.mImgFileList):
                filename = self.mImgFileList[currIndex + 1]

        if filename:
            self.loadFile(filename)

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = os.path.dirname(ustr(self.imgFilePath)) if self.imgFilePath else '.'
        formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        filters = "Image & Attribute files (%s)" % ' '.join(formats + ['*%s' % AttributeFile.suffix])
        filename = QFileDialog.getOpenFileName(self, '%s - Choose Image or Label file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.loadFile(filename)

    def saveFile(self, _value=False):
        if self.defaultSaveDir is not None and len(ustr(self.defaultSaveDir)):
            if self.imgFilePath:
                imgFileName = os.path.basename(self.imgFilePath)
                savedFileName = os.path.splitext(imgFileName)[0]
                savedPath = os.path.join(ustr(self.defaultSaveDir), savedFileName)
                self._saveFile(savedPath)
        else:
            imgFileDir = os.path.dirname(self.imgFilePath)
            imgFileName = os.path.basename(self.imgFilePath)
            savedFileName = os.path.splitext(imgFileName)[0]
            savedPath = os.path.join(imgFileDir, savedFileName)
            self._saveFile(savedPath if self.attributeFile else self.saveFileDialog(removeExt=False))

    def saveFileDialog(self, removeExt=True):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % AttributeFile.suffix
        openDialogPath = self.currentPath()
        dlg = QFileDialog(self, caption, openDialogPath, filters)
        dlg.setDefaultSuffix(AttributeFile.suffix[1:])
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filenameWithoutExtension = os.path.splitext(self.imgFilePath)[0]
        dlg.selectFile(filenameWithoutExtension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            fullFilePath = ustr(dlg.selectedFiles()[0])
            if removeExt:
                return os.path.splitext(fullFilePath)[0] # Return file path without the extension.
            else:
                return fullFilePath
        return ''

    def _saveFile(self, attributeJSONFilePath):
        if attributeJSONFilePath and self.saveAttributes(attributeJSONFilePath):
            self.setClean()
            self.statusBar().showMessage('Saved to  %s' % attributeJSONFilePath)
            self.statusBar().show()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)

    def resetAll(self):
        self.settings.reset()
        self.close()
        proc = QProcess()
        proc.startDetached(os.path.abspath(__file__))

    def mayContinue(self):
        if not self.dirty:
            return True
        else:
            discardChanges = self.discardChangesDialog()
            if discardChanges == QMessageBox.No:
                return True
            elif discardChanges == QMessageBox.Yes:
                self.saveFile()
                return True
            else:
                return False

    def discardChangesDialog(self):
        yes, no, cancel = QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel
        msg = u'You have unsaved changes, would you like to save them and proceed?\nClick "No" to undo all changes.'
        return QMessageBox.warning(self, u'Attention', msg, yes | no | cancel)

    def errorMessage(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(self.imgFilePath) if self.imgFilePath else '.'

    def deleteSelectedAttribute(self):
        pass

    def loadJsonByFilename(self, jsonPath):
        if not os.path.isfile(jsonPath):
            jsonNewWriter = AttributeJSONWriter(jsonPath, attributeDict={})
            jsonNewWriter.write()
            self.attributeDict = {}
        jsonParseReader = AttributeJSONReader(jsonPath)
        self.loadAttributes(jsonParseReader.attributeDict)

def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("app"))
    # Tzutalin 201705+: Accept extra arguments to change predefined class file
    argparser = argparse.ArgumentParser()
    argparser.add_argument("image_dir", nargs="?")
    argparser.add_argument("save_dir", nargs="?")
    args = argparser.parse_args(argv[1:])
    # Usage : labelImg.py image predefClassFile saveDir
    win = MainWindow(args.image_dir, args.save_dir)
    win.show()
    return app, win


def main():
    '''construct main app and run it'''
    app, _win = get_main_app(sys.argv)
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main())
