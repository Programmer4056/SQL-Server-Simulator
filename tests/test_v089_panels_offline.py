"""Regression checks for visible/closable panels and offline Windows packaging."""
from pathlib import Path
import os
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from version_info import APP_VERSION
from locale_support import ui


class OfflinePackagingTests(unittest.TestCase):
    def test_onefile_builder_is_self_contained_and_never_downloads(self):
        script=(ROOT/'build_windows_offline.bat').read_text(encoding='utf-8')
        self.assertIn('--onefile',script)
        self.assertIn('--windowed',script)
        self.assertIn('--add-data',script)
        self.assertIn('PySide6.QtWidgets',script)
        self.assertNotIn('-m pip install',script)
        self.assertIn('dist_offline\\SQLServerSimulator_Offline_v0.8.9.exe',script)

    def test_release_consistency_and_ui_translations(self):
        self.assertEqual(APP_VERSION, '0.8.9')
        for label in ('Show SQL Editor','Show Database Diagram',
                      'Show Welcome Screen','Show All Panels'):
            self.assertNotEqual(ui(label,'fa'),label)
        self.assertIn('dist_offline/*.exe',
                      (ROOT/'.github/workflows/cross-platform-build.yml').read_text())


try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from app import MainWindow, ClearDockTitleBar
    HAS_QT=True
except ImportError:
    HAS_QT=False


@unittest.skipUnless(HAS_QT, 'PySide6 is not installed in this environment')
class PanelUiTests(unittest.TestCase):
    def test_panels_have_visible_buttons_and_can_reopen(self):
        app=QApplication.instance() or QApplication([])
        win=MainWindow()
        win.show()
        app.processEvents()
        for dock in (win.leftdock, win.rightdock, win.bottomdock):
            head=dock.titleBarWidget()
            self.assertIsInstance(head,ClearDockTitleBar)
            self.assertEqual(head.close_button.text(),'×')
            self.assertGreaterEqual(head.close_button.width(),30)
            head.close_button.click()
            app.processEvents()
            self.assertTrue(dock.isHidden())
        win.show_all_panels()
        app.processEvents()
        for dock in (win.leftdock, win.rightdock, win.bottomdock):
            self.assertFalse(dock.isHidden())
        win.close()

    def test_close_query_and_diagram_tabs_and_restore_without_losing_content(self):
        app=QApplication.instance() or QApplication([])
        win=MainWindow()
        win.show()
        win.editor.setPlainText('SELECT 729;')
        for page in (win.query_page,win.diagram_page):
            index=win.tabs.indexOf(page)
            self.assertGreaterEqual(index,0)
            button=win.tabs.tabBar().tabButton(index, win.tabs.tabBar().ButtonPosition.RightSide)
            self.assertIsNotNone(button)
            self.assertEqual(button.text(),'×')
            button.click()
            self.assertEqual(win.tabs.indexOf(page),-1)
            win.activate_main_tab(page)
            self.assertGreaterEqual(win.tabs.indexOf(page),0)
            self.assertIs(win.tabs.currentWidget(),page)
        self.assertEqual(win.editor.toPlainText(),'SELECT 729;')
        win.close()

    def test_farsi_titles_and_reopen_actions(self):
        app=QApplication.instance() or QApplication([])
        win=MainWindow()
        win.show()
        win.lang='fa'
        win.retranslate()
        self.assertEqual(win.leftdock.titleBarWidget().caption.text(),win.text('object_explorer'))
        self.assertIn('بازکردن',win.leftdock.titleBarWidget().close_button.toolTip())
        view=next(m for m in win.menuBar().actions() if m.text()==win.text('view')).menu()
        self.assertTrue(any(a.text()==ui('Show Database Diagram','fa') for a in view.actions()))
        win.close()

if __name__=='__main__':unittest.main()
