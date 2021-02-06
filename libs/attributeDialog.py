try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.utils import newIcon, labelValidator
from libs.stringBundle import StringBundle

BB = QDialogButtonBox

class AttributeDialog(QDialog):

    def __init__(self, parent=None):
        super(AttributeDialog, self).__init__(parent)

        # Load string bundle for i18n
        self.stringBundle = StringBundle.getBundle()
        getStr = lambda strId: self.stringBundle.getString(strId)
        text = getStr('enterPhotoAttribute')

        self.edit = QLineEdit()
        self.edit.setText(text)
        self.edit.setValidator(labelValidator())
        self.edit.editingFinished.connect(self.postProcess)

        layout = QVBoxLayout()
        layout.addWidget(self.edit)
        self.buttonBox = bb = BB(BB.Ok | BB.Cancel, Qt.Horizontal, self)
        bb.button(BB.Ok).setIcon(newIcon('done'))
        bb.button(BB.Cancel).setIcon(newIcon('undo'))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)
        self.setLayout(layout)

    def validate(self):
        try:
            if self.edit.text().trimmed():
                self.accept()
        except AttributeError:
            # PyQt5: AttributeError: 'str' object has no attribute 'trimmed'
            if self.edit.text().strip():
                self.accept()

    def postProcess(self):
        try:
            self.edit.setText(self.edit.text().trimmed())
        except AttributeError:
            # PyQt5: AttributeError: 'str' object has no attribute 'trimmed'
            self.edit.setText(self.edit.text())

    def popUp(self, text='', move=True):
        self.edit.setText(text)
        self.edit.setSelection(0, len(text))
        self.edit.setFocus(Qt.PopupFocusReason)
        if move:
            cursor_pos = QCursor.pos()
            parent_bottomRight = self.parentWidget().geometry()
            max_x = parent_bottomRight.x() + parent_bottomRight.width() - self.sizeHint().width()
            max_y = parent_bottomRight.y() + parent_bottomRight.height() - self.sizeHint().height()
            max_global = self.parentWidget().mapToGlobal(QPoint(max_x, max_y))
            if cursor_pos.x() > max_global.x():
                cursor_pos.setX(max_global.x())
            if cursor_pos.y() > max_global.y():
                cursor_pos.setY(max_global.y())
            self.move(cursor_pos)

        return self.edit.text() if self.exec_() else None


class AttributeDisabledMessageBox(QMessageBox):
    def __init__(self, parent=None):
        super(AttributeDisabledMessageBox, self).__init__(parent)
        # Load string bundle for i18n
        self.stringBundle = StringBundle.getBundle()
        getStr = lambda strId: self.stringBundle.getString(strId)

        self.setIcon(QMessageBox.Critical)
        self.setText(getStr('disabledEditingWarning'))

    def popUp(self, move=True):
        if move:
            cursor_pos = QCursor.pos()
            parent_bottomRight = self.parentWidget().geometry()
            max_x = parent_bottomRight.x() + parent_bottomRight.width() - self.sizeHint().width()
            max_y = parent_bottomRight.y() + parent_bottomRight.height() - self.sizeHint().height()
            max_global = self.parentWidget().mapToGlobal(QPoint(max_x, max_y))
            if cursor_pos.x() > max_global.x():
                cursor_pos.setX(max_global.x())
            if cursor_pos.y() > max_global.y():
                cursor_pos.setY(max_global.y())
            self.move(cursor_pos)

        return self.text() if self.exec_() else None