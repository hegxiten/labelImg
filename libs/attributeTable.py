try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.stringBundle import StringBundle
import sys


class AttributeTable(QTableWidget):

    def __init__(self, *args, **kwargs):
        super(AttributeTable, self).__init__(*args, **kwargs)
        self.tableIdxClipboard = None
        self.tableDataClipboard = None

    def keyPressEvent(self, event):
        super(AttributeTable, self).keyPressEvent(event)
        if event.key() == Qt.Key_C and (event.modifiers() & Qt.ControlModifier):
            self.tableIdxClipboard = sorted(self.selectedIndexes())
            self.tableDataClipboard = [cell.data() for cell in self.selectedIndexes()]

        elif event.key() == Qt.Key_V and (event.modifiers() & Qt.ControlModifier):
            r = self.currentRow() - self.tableIdxClipboard[0].row()
            c = self.currentColumn() - self.tableIdxClipboard[0].column()
            for cellIdx in range(len(self.tableIdxClipboard)):
                cell, cellData = self.tableIdxClipboard[cellIdx], self.tableDataClipboard[cellIdx]
                self.setItem(cell.row() + r, cell.column() + c, QTableWidgetItem(cellData))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = AttributeTable()
    gui.show()
    sys.exit(app.exec_())