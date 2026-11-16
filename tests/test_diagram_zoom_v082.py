"""Diagram zoom regression, including extremely small scales after Auto Layout."""
from __future__ import annotations
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

try:
    from PySide6.QtWidgets import QApplication,QPushButton,QLabel
    from core import LabDatabase,Column
    from widgets import Diagram
    from app import MainWindow
    HAS_QT=True
except ImportError:
    HAS_QT=False


class SourceZoomTests(unittest.TestCase):
    """Checks that still execute on machines without Qt installed."""
    def test_zoom_is_not_stuck_at_old_twenty_percent_limit(self):
        source=(ROOT/'src/widgets.py').read_text(encoding='utf-8')
        self.assertNotIn('0.20<=current*factor<=4.0',source)
        self.assertIn('def zoom_in(self):',source)
        self.assertIn('def zoom_out(self):',source)
        self.assertIn('def zoom_by(self, factor',source)

    def test_toolbar_controls_are_connected_and_localized(self):
        app=(ROOT/'src/app.py').read_text(encoding='utf-8')
        translations=(ROOT/'src/i18n.py').read_text(encoding='utf-8')
        for label in ('diagramZoomInButton','diagramZoomOutButton','diagramZoomPercent'):
            self.assertIn(label,app)
        self.assertIn('self.diagram.zoom_in',app)
        self.assertIn('self.diagram.zoom_out',app)
        for translation in ('Zoom In','Zoom Out','بزرگ‌نمایی','کوچک‌نمایی'):
            self.assertIn(translation,translations)


@unittest.skipUnless(HAS_QT,'PySide6 unavailable; run these tests during Windows/macOS/Linux build')
class QtZoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_auto_layout_with_many_tables_allows_zoom_in_and_out(self):
        with tempfile.TemporaryDirectory() as folder:
            db=LabDatabase(Path(folder)/'large_diagram.db')
            view=Diagram()
            try:
                for index in range(60):
                    db.create_table(f'Table{index:02}',[Column('ID','INT',True,True,True)])
                view.resize(900,570)
                view.show()
                view.set_db(db)
                self.app.processEvents()
                view.auto_layout()
                self.app.processEvents()
                fitted=view.zoom_level()
                self.assertLess(fitted,0.20,'test should reproduce a scale below the old zoom limit')
                self.assertTrue(view.zoom_in())
                self.assertGreater(view.zoom_level(),fitted)
                self.assertTrue(view.zoom_out())
                self.assertAlmostEqual(view.zoom_level(),fitted,places=5)
                view.zoom_actual()
                self.assertAlmostEqual(view.zoom_level(),1.0,places=5)
                self.assertTrue(view.zoom_out())
                self.assertLess(view.zoom_level(),1.0)
            finally:
                view.close()
                db.close()

    def test_zoom_buttons_and_percentage_are_wired(self):
        win=MainWindow()
        try:
            win.show()
            self.app.processEvents()
            zoom_in=win.findChild(QPushButton,'diagramZoomInButton')
            zoom_out=win.findChild(QPushButton,'diagramZoomOutButton')
            status=win.findChild(QLabel,'diagramZoomPercent')
            self.assertIsNotNone(zoom_in)
            self.assertIsNotNone(zoom_out)
            self.assertIsNotNone(status)
            original=win.diagram.zoom_level()
            zoom_in.click()
            self.assertGreater(win.diagram.zoom_level(),original)
            self.assertIn('125',status.text())
            zoom_out.click()
            self.assertAlmostEqual(win.diagram.zoom_level(),original,places=5)
            self.assertEqual(status.text(),'100%')
            win.lang='fa'
            win.retranslate()
            self.assertIn('بزرگ',zoom_in.text())
            self.assertIn('کوچک',zoom_out.text())
        finally:
            win.close()


if __name__=='__main__':
    unittest.main()
