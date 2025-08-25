import pyqtgraph as pg
from pyqtgraph.Qt import QtGui

class GraphWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None, **kargs):
        pg.setConfigOptions(antialias=True)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        pg.GraphicsLayoutWidget.__init__(self, **kargs)
        self.setParent(parent)
        self.setWindowTitle('Acquisition')
    
if __name__ == '__main__':
    w = GraphWidget()
    w.show()
    QtGui.QApplication.instance().exec_()