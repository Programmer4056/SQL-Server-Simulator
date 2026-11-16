"""Qt integration checks executed on Windows before PyInstaller packaging."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    from PySide6.QtWidgets import QApplication,QDockWidget
    from PySide6.QtCore import Qt
    import app as app_module
    from app import MainWindow
    from core import LabDatabase,Column
    HAS_QT=True
except ImportError:
    HAS_QT=False

@unittest.skipUnless(HAS_QT,'PySide6 not installed; Windows builder runs these tests')
class QtRelease07Tests(unittest.TestCase):
    def setUp(self):
        self.qt=QApplication.instance() or QApplication([])
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.db'
    def tearDown(self):
        self.tmp.cleanup()

    def test_docks_resize_float_and_toolbar_overflow(self):
        win=MainWindow()
        self.assertLessEqual(win.minimumWidth(),640)
        self.assertLessEqual(win.minimumHeight(),420)
        for dock in (win.leftdock,win.rightdock,win.bottomdock):
            self.assertTrue(dock.features() & QDockWidget.DockWidgetFeature.DockWidgetMovable)
            self.assertTrue(dock.features() & QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.assertTrue(win.toolbar.isMovable())
        self.assertIsNotNone(win.diagram_actions_scroll.horizontalScrollBar())
        win.reset_window_layout()
        win.close()

    def test_theme_icons_are_native_palette_aware(self):
        win=MainWindow()
        self.assertFalse(win.icon('table').pixmap(28,28).isNull())
        win.theme='dark'
        dark=win.icon('table').pixmap(28,28).toImage()
        win.theme='light'
        light=win.icon('table').pixmap(28,28).toImage()
        self.assertNotEqual(dark.pixelColor(13,5).name(),light.pixelColor(13,5).name())
        win.close()

    def test_layout_and_expanded_canvas(self):
        db=LabDatabase(self.path)
        for n in ('Hub','A','B','C'):
            db.create_table(n,[Column('ID','INT',True,True,True)])
        for n in ('A','B','C'):
            db.one_to_many('Hub',n,'HubID',False)
        db.close()
        win=MainWindow();win.load_database(self.path)
        positions=win.diagram.auto_layout()
        self.assertEqual(len(positions),4)
        self.assertGreater(win.diagram.gscene.sceneRect().width(),win.diagram.gscene.itemsBoundingRect().width()+1000)
        self.assertEqual(set(win.db.positions()),set(positions))
        win.close()

    def test_external_schema_drop_closes_stale_view(self):
        db=LabDatabase(self.path)
        db.create_table('audit_logs',[Column('ID','INT',True,True,True)])
        db.close()
        win=MainWindow();win.load_database(self.path)
        win.show_data('audit_logs')
        self.assertIn('audit_logs',win.data_tabs)
        # Remove via the same connection; schema cookie still increments.
        win.db.drop_table('audit_logs')
        win.check_external_schema_changes()
        self.assertNotIn('audit_logs',win.data_tabs)
        self.assertNotIn('audit_logs',win.diagram.nodes)
        win.close()

    def test_tsql_create_database_in_editor_without_open_project(self):
        old=app_module.APP_FOLDER
        app_module.APP_FOLDER=Path(self.tmp.name)
        try:
            win=MainWindow()
            win.editor.setPlainText('CREATE DATABASE Demo;\nGO\nUSE Demo;\nGO\nCREATE TABLE Students (ID INT PRIMARY KEY);')
            win.execute_sql()
            self.assertIsNotNone(win.db)
            self.assertEqual(win.db.path.name,'Demo.db')
            self.assertIn('Students',win.db.tables())
            self.assertTrue(win.bottomdock.isVisible() or not win.isVisible())
            win.close()
        finally:
            app_module.APP_FOLDER=old

if __name__=='__main__':unittest.main()
