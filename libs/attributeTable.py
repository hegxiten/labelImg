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
        self.copied_cells = None

    def keyPressEvent(self, event):
        super(AttributeTable, self).keyPressEvent(event)
        if event.key() == Qt.Key_C and (event.modifiers() & Qt.ControlModifier):
            self.copied_cells = sorted(self.selectedIndexes())
        elif event.key() == Qt.Key_V and (event.modifiers() & Qt.ControlModifier):
            r = self.currentRow() - self.copied_cells[0].row()
            c = self.currentColumn() - self.copied_cells[0].column()
            for cell in self.copied_cells:
                self.setItem(cell.row() + r, cell.column() + c, QTableWidgetItem(cell.data()))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = AttributeTable()
    gui.show()
    sys.exit(app.exec_())