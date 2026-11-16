"""Prevent English table-designer controls leaking into Persian mode."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from i18n import tr
from locale_support import ui

class TableDesignerFaLocalizationTests(unittest.TestCase):
    def test_new_and_existing_table_button_texts(self):
        self.assertEqual(tr('save_table','fa'),'ساخت جدول')
        self.assertEqual(tr('save_changes','fa'),'ذخیره تغییرات')
        self.assertEqual(tr('save_changes','en'),'Save Changes')
        self.assertEqual(tr('cancel','fa'),'انصراف')

    def test_related_tooltips_translated(self):
        for label in ('Double-click a name to rename. Existing data are migrated safely when possible.',
                      'Identity Specification: Seed / Increment'):
            self.assertNotEqual(ui(label,'fa'),label)

    def test_table_designer_uses_translation_not_hardcoded_save_label(self):
        code=(ROOT/'src/dialogs.py').read_text(encoding='utf-8')
        self.assertIn("tr('save_changes',lang) if table else tr('save_table',lang)",code)
        self.assertNotIn("'Save Changes' if table",code)

try:
    from PySide6.QtWidgets import QApplication, QDialogButtonBox
    from dialogs import TableDesigner
    from core import LabDatabase, Column
    import tempfile
    HAS_QT=True
except ImportError:
    HAS_QT=False

@unittest.skipUnless(HAS_QT,'PySide6 is not installed')
class TableDesignerQtTests(unittest.TestCase):
    def test_buttons_use_persian_for_existing_table(self):
        with tempfile.TemporaryDirectory() as temp:
            app=QApplication.instance() or QApplication([])
            db=LabDatabase(Path(temp)/'test.db')
            db.create_table('students',[Column('id','INT',True,True,True)])
            designer=TableDesigner(db,'fa',lambda:None,table='students')
            box=designer.findChild(QDialogButtonBox)
            self.assertEqual(box.button(QDialogButtonBox.StandardButton.Ok).text(),'ذخیره تغییرات')
            designer.close();db.close()

if __name__=='__main__':unittest.main()
