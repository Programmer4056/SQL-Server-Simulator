"""Run these tests with PySide6 on Windows/macOS/Linux (offscreen is sufficient)."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QKeySequence
    from PySide6.QtCore import Qt
    from widgets import SQLEditor
    from app import MainWindow
    HAS_QT=True
except ImportError:
    HAS_QT=False
from core import LabDatabase, Column

@unittest.skipUnless(HAS_QT,'PySide6 absent; run the GUI tests on the target OS')
class EditorZoomAndCompletionQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.window=MainWindow()
        self.window.show()
        self.window.tabs.setCurrentWidget(self.window.query_page)
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_buttons_and_min_max_zoom(self):
        editor=self.window.editor
        original=editor.font_point_size
        self.window.query_zoom_in_button.click()
        self.assertEqual(editor.font_point_size,original+1)
        self.window.query_zoom_out_button.click()
        self.assertEqual(editor.font_point_size,original)
        editor.set_zoom(999)
        self.assertEqual(editor.font_point_size,editor.MAX_FONT)
        editor.set_zoom(-999)
        self.assertEqual(editor.font_point_size,editor.MIN_FONT)
        self.window.query_zoom_reset_button.click()
        self.assertEqual(editor.font_point_size,editor.DEFAULT_FONT)
        self.assertEqual(self.window.query_zoom_percent.text(),'100%')

    def test_keyboard_shortcuts_available_on_both_tabs(self):
        for shortcuts in (self.window._query_shortcuts,self.window._diagram_shortcuts):
            sequences={s.key().toString(QKeySequence.SequenceFormat.PortableText)
                       for s in shortcuts}
            self.assertIn('Ctrl++',sequences)
            self.assertIn('Ctrl+=',sequences)
            self.assertIn('Ctrl+-',sequences)
            self.assertIn('Ctrl+0',sequences)
            for shortcut in shortcuts:
                self.assertEqual(shortcut.context(),Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def test_completion_offers_schema_and_inserts_selected_table(self):
        with tempfile.TemporaryDirectory() as dirname:
            db=LabDatabase(Path(dirname)/'students.db')
            db.create_table('Student',[Column('ID','INT',True,True,True),Column('FullName','NVARCHAR(50)')])
            try:
                editor=self.window.editor
                editor.set_database(db)
                self.assertIn('Student',editor._completion_candidates('Stu'))
                editor.setPlainText('SELECT * FROM Stu')
                editor.moveCursor(editor.textCursor().MoveOperation.End)
                self.assertEqual(editor._word_prefix(),'Stu')
                editor.insert_completion('Student')
                self.assertEqual(editor.toPlainText(),'SELECT * FROM Student')
                editor.setPlainText('Student.Ful')
                editor.moveCursor(editor.textCursor().MoveOperation.End)
                self.assertIn('FullName',editor._completion_candidates('Ful'))
            finally:
                editor.set_database(None)
                db.close()

if __name__=='__main__':unittest.main()
