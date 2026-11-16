"""Build-blocking regressions identified on Windows 11 / Python 3.12.

Qt tests execute in the Windows builder's offscreen preflight and skip only
when PySide6 is unavailable in the current environment.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

try:
    from PySide6.QtWidgets import QApplication, QFrame, QLabel
    from widgets import WelcomePanel
    from dialogs import GridRowEditor
    from core import LabDatabase, Column
    from style import make_qss
    HAS_QT=True
except ImportError:
    HAS_QT=False


@unittest.skipUnless(HAS_QT, 'PySide6 required for UI build preflight')
class BuildFixUIRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def test_welcome_card_stays_responsive_and_credits_wrap(self):
        for lang in ('fa','en'):
            panel=WelcomePanel(lang,lambda:None,lambda:None,lambda:None)
            panel.setStyleSheet(make_qss('dark'))
            try:
                for width,height in ((360,420),(530,490),(950,700)):
                    panel.resize(width,height)
                    panel.show()
                    self.qt.processEvents()
                    self.qt.processEvents()
                    card=panel.findChild(QFrame,'welcomeCard')
                    detail=(f'{lang=} {width=} {height=} actual={card.width()} '
                            f'min={card.minimumWidth()} max={card.maximumWidth()} '
                            f'viewport={panel._welcome_scroll.viewport().width()} '
                            f'layout_min={card.layout().minimumSize().width()}')
                    self.assertLessEqual(card.width(),448,detail)
                    self.assertLessEqual(card.width(),max(220,width-36),detail)
                    # Layout constraints must never silently increase minimum width.
                    self.assertEqual(card.minimumWidth(),card.maximumWidth(),detail)
                    self.assertLessEqual(panel._welcome_container.minimumWidth(),
                                         card.width()+36,detail)
                    self.assertGreaterEqual(card.height(),392)
                    self.assertGreaterEqual(card.height(),card.layout().minimumSize().height())
                    title=panel.findChild(QLabel,'welcomeTitle')
                    self.assertTrue(title.wordWrap())
                    self.assertGreaterEqual(title.height(),title.minimumHeight())
                    authors=panel.findChildren(QLabel,'welcomeAuthor')
                    self.assertEqual(len(authors),2)
                    self.assertTrue(all(a.wordWrap() and a.height()>=a.minimumHeight()
                                        for a in authors))
            finally:
                panel.close()

    def test_queued_edit_refresh_cannot_access_closed_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=LabDatabase(Path(tmp)/'Rows.sqlite')
            try:
                db.create_table('Student',[Column('ID','INT',True,True,True),
                                           Column('Name','NVARCHAR(50)')])
                dialog=GridRowEditor(db,'Student','en',lambda:None)
                dialog._refresh_timer.start(0)
                dialog.close()
                self.assertFalse(dialog._refresh_timer.isActive())
            finally:
                db.close()
            # On Windows the temporary database must be removable here.
            self.qt.processEvents()

if __name__=='__main__':
    unittest.main()
