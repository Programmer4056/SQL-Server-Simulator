"""Regression for v0.6.1: mouse-following preview must not hide target fields."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    from PySide6.QtCore import Qt,QPointF
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QLabel,QScrollArea
    from core import LabDatabase,Column
    from widgets import Diagram,WelcomePanel
    from style import make_qss
    HAS_QT=True
except ImportError:
    HAS_QT=False

@unittest.skipUnless(HAS_QT,'Qt not installed; Windows build runs the interaction tests')
class ClickToLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.tmp.name)/'links.db')
        self.db.create_table('Department',[Column('ID','INT',True,True,True)])
        self.db.create_table('Student',[Column('ID','INT',True,True,True),Column('DepartmentID','INT')])
        self.received=[]
        self.diagram=Diagram()
        self.diagram.resize(1050,650)
        self.diagram.set_actions(on_field_connect=lambda *items:self.received.append(items))
        self.diagram.set_db(self.db)
        self.diagram.show()
        QApplication.processEvents()

    def tearDown(self):
        self.diagram.close()
        self.db.close()
        self.tmp.cleanup()

    def fieldpos(self,table,field):
        node=self.diagram.nodes[table]
        return self.diagram.mapFromScene(node.mapToScene(QPointF(40,node.column_y(field))))

    def test_preview_is_below_cards_and_ignorable_at_cursor(self):
        self.diagram.start_manual_drawing(True)
        src=self.fieldpos('Department','ID')
        dst=self.fieldpos('Student','DepartmentID')
        QTest.mouseClick(self.diagram.viewport(),Qt.MouseButton.LeftButton,pos=src)
        self.assertEqual(self.diagram.click_anchor,('Department','ID'))
        QTest.mouseMove(self.diagram.viewport(),pos=dst)
        self.assertIs(self.diagram.node_at(dst),self.diagram.nodes['Student'])
        QTest.mouseClick(self.diagram.viewport(),Qt.MouseButton.LeftButton,pos=dst)
        self.assertEqual(self.received,[('Department','ID','Student','DepartmentID')])

    def test_direct_column_drag(self):
        src=self.fieldpos('Department','ID')
        dst=self.fieldpos('Student','DepartmentID')
        QTest.mousePress(self.diagram.viewport(),Qt.MouseButton.LeftButton,pos=src)
        QTest.mouseMove(self.diagram.viewport(),pos=dst)
        QTest.mouseRelease(self.diagram.viewport(),Qt.MouseButton.LeftButton,pos=dst)
        self.assertEqual(self.received,[('Department','ID','Student','DepartmentID')])

    def test_welcome_no_small_label_heights(self):
        for lang in ('en','fa'):
            for theme in ('light','dark'):
                QApplication.instance().setStyleSheet(make_qss(theme))
                panel=WelcomePanel(lang,lambda:None,lambda:None,lambda:None)
                panel.resize(530,490)
                panel.show()
                QApplication.processEvents()
                title=panel.findChild(QLabel,'welcomeTitle')
                desc=panel.findChild(QLabel,'welcomeDescription')
                self.assertGreaterEqual(title.height(),135)
                self.assertGreaterEqual(desc.height(),115)
                self.assertTrue(panel.findChild(QScrollArea,'welcomeScroll'))
                panel.close()

if __name__=='__main__':unittest.main()
