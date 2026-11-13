"""Run with PySide6 (Windows build preflight); validates diagram actions and welcome."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    from PySide6.QtWidgets import QApplication,QLabel,QScrollArea
    from app import MainWindow
    from widgets import WelcomePanel
    from core import LabDatabase,Column
    HAS_QT=True
except ImportError:
    HAS_QT=False

@unittest.skipUnless(HAS_QT,'Qt not installed; Windows build will run these tests')
class NewDiagramUI(unittest.TestCase):
    def make_db(self,path):
        db=LabDatabase(path)
        db.create_table('Department',[Column('ID','INT',True,True,True)])
        db.create_table('Student',[Column('ID','INT',True,True,True),Column('DepartmentID','INT')])
        db.connect_fields('Department','ID','Student','DepartmentID','1:N')
        db.close()

    def test_line_selection_enables_delete_button_and_refresh_clears(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'visual.db';self.make_db(path)
            window=MainWindow();window.load_database(path)
            edge=next(e for e in window.diagram.edges if e.link.get('fk_id') is not None)
            window.diagram.select_edge(edge)
            self.assertTrue(window.delete_link_button.isEnabled())
            self.assertTrue(edge.selected)
            window.diagram.select_edge(None)
            self.assertFalse(window.delete_link_button.isEnabled())
            window.close()

    def test_manual_click_mode_can_be_toggled(self):
        app=QApplication.instance() or QApplication([])
        window=MainWindow()
        window.draw_link_button.setChecked(True)
        self.assertTrue(window.diagram.manual_click_mode)
        window.draw_link_button.setChecked(False)
        self.assertFalse(window.diagram.manual_click_mode)
        window.close()

    def test_welcome_english_and_farsi_keep_separate_readable_labels(self):
        app=QApplication.instance() or QApplication([])
        for lang in ('en','fa'):
            widget=WelcomePanel(lang,lambda:None,lambda:None,lambda:None)
            self.assertIsNotNone(widget.findChild(QScrollArea,'welcomeScroll'))
            title=widget.findChild(QLabel,'welcomeTitle')
            author=widget.findChild(QLabel,'welcomeAuthor')
            notice=widget.findChild(QLabel,'welcomeNotice')
            self.assertTrue(title.wordWrap())
            self.assertTrue(notice.wordWrap())
            self.assertNotEqual(author.text(),notice.text())
            widget.close()

if __name__=='__main__':unittest.main()
