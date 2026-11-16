"""Qt integration checks; run on each release runner with QT_QPA_PLATFORM=offscreen."""
import os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    from PySide6.QtWidgets import QApplication,QLabel,QFrame,QTableWidget
    from PySide6.QtCore import Qt,QTimer
    from app import MainWindow
    from dialogs import ScriptExportWizard,GridRowEditor,RelationshipWizard
    from widgets import WelcomePanel
    HAS_QT=True
except ImportError:
    HAS_QT=False
from core import LabDatabase, Column
from model_ext import insert_data

@unittest.skipUnless(HAS_QT,'PySide6 is unavailable; run this on the target OS')
class V085QtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.tmp.name)/'test.db')
        self.db.create_table('Student',[Column('ID','INT',True,True,True),Column('FullName','NVARCHAR(50)')])
        insert_data(self.db,'Student',{'FullName':'Ali'})
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def test_generate_script_opens_in_editor(self):
        output=[]
        wizard=ScriptExportWizard(self.db,'fa',on_open=output.append)
        wizard.open_radio.setChecked(True)
        self.assertTrue(wizard.open_radio.isChecked())
        with patch('dialogs.info'):
            wizard.accept()
        self.assertEqual(len(output),1)
        self.assertIn('CREATE TABLE',output[0].upper())
    def test_grid_cell_edit_without_dialog(self):
        widget=GridRowEditor(self.db,'Student','fa',lambda:None)
        try:
            self.assertFalse(bool(widget.grid.item(0,0).flags()&Qt.ItemFlag.ItemIsEditable))
            self.assertTrue(bool(widget.grid.item(0,1).flags()&Qt.ItemFlag.ItemIsEditable))
            widget.grid.item(0,1).setText('Sara')
            self.assertEqual(self.db.connection.execute('SELECT FullName FROM Student').fetchone()[0],'Sara')
        finally:widget.close()
    def test_relationship_wizard_exposes_composite_child_strategy(self):
        self.db.create_table('Dept',[Column('ID','INT',True)])
        wizard=RelationshipWizard(self.db,'fa',lambda:None)
        self.assertEqual(wizard.child_pk_strategy.count(),2)
        self.assertEqual(wizard.child_pk_strategy.itemData(1),'composite')
    def test_compact_welcome(self):
        panel=WelcomePanel('fa',lambda:None,lambda:None,lambda:None)
        card=panel.findChild(QFrame,'welcomeCard')
        self.assertLessEqual(card.maximumWidth(),480)
        # No fixed maximum height: translated text/QA credits must be able
        # to grow and scroll instead of being clipped on high-DPI displays.
        self.assertGreaterEqual(card.minimumHeight(),392)
        self.assertTrue(panel.findChild(QFrame,'welcomeCard').layout() is not None)
        panel.close()
    def test_persian_email_template_and_script_action(self):
        main=MainWindow()
        try:
            main.lang='fa'
            subject,body=main.bug_email_draft()
            self.assertIn('گزارش',subject)
            self.assertIn('مراحل بازتولید خطا',body)
            self.assertIn('Ctrl++',{s.key().toString() for s in main._query_shortcuts})
        finally:main.close()

if __name__=='__main__':unittest.main()
