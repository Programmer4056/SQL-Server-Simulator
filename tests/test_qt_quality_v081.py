"""UI regressions run with PySide6 on each target OS before packaging.

These tests are skipped rather than falsely marked as passed when Qt is absent.
"""
import os
import sys
import unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea, QMessageBox, QLabel
    from PySide6.QtGui import QFontMetrics
    from app import MainWindow
    from version_info import APP_VERSION
    HAS_QT=True
except ImportError:
    HAS_QT=False

@unittest.skipUnless(HAS_QT,'PySide6 not installed; execute on Windows/macOS/Linux build runner')
class VisualReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.win=MainWindow()
        self.win.resize(850,610)
        self.win.show()
        self.app.processEvents()

    def tearDown(self):
        self.win.close()
        self.app.processEvents()

    def test_all_diagram_buttons_keep_complete_labels(self):
        buttons=self.win.diagram_action_host.findChildren(QPushButton)
        self.assertGreaterEqual(len(buttons),8)
        for button in buttons:
            needed=QFontMetrics(button.font()).horizontalAdvance(button.text())+20
            self.assertGreaterEqual(button.minimumWidth(),needed,button.text())
            self.assertGreaterEqual(button.height(),40,button.text())

    def test_overflow_scroll_works_on_small_window(self):
        scroll=self.win.diagram_actions_scroll
        self.app.processEvents()
        self.assertGreater(self.win.diagram_action_host.width(),scroll.viewport().width())
        self.assertGreater(scroll.horizontalScrollBar().maximum(),0)

    def test_about_correct_in_persian_and_english(self):
        for language in ('fa','en'):
            self.win.lang=language
            self.win.retranslate()
            # Inspect the same localized HTML that MainWindow.about() passes
            # to QMessageBox.about(), without opening a blocking native dialog.
            html=self.win.text('about_text')
            self.assertIn('v'+APP_VERSION,html)
            self.assertIn('dir="rtl"' if language=='fa' else 'dir="ltr"',html)

    def test_language_change_preserves_database_title(self):
        # The title must preserve the active DB name during retranslation.
        import tempfile
        from pathlib import Path
        from core import LabDatabase
        with tempfile.TemporaryDirectory() as tmp:
            name=Path(tmp)/'Teaching.sqlite'
            db=LabDatabase(name);db.close()
            try:
                self.win.load_database(name)
                self.win.lang='fa'
                self.win.retranslate()
                self.assertIn('Teaching',self.win.windowTitle())
                self.assertIn(APP_VERSION,self.win.windowTitle())
            finally:
                # On Windows, temporary DB files cannot be removed until
                # every sqlite3 connection has been closed. tearDown runs
                # after this TemporaryDirectory context is exited.
                self.win.close_database()

    def test_welcome_labels_fit_without_clipping(self):
        from widgets import WelcomePanel
        for language in ('fa','en'):
            panel=WelcomePanel(language,lambda:None,lambda:None,lambda:None)
            panel.resize(530,490)
            panel.show()
            self.app.processEvents()
            for label_name in ('welcomeTitle','welcomeDescription'):
                label=panel.findChild(QLabel,label_name)
                self.assertTrue(label.isVisible(),label_name)
                self.assertGreaterEqual(label.height(),label.minimumHeight())
            self.assertIsNotNone(panel.findChild(QScrollArea,'welcomeScroll'))
            panel.close()

if __name__=='__main__': unittest.main()
