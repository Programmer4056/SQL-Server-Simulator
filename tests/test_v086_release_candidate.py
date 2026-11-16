"""Release-candidate tests for parent checks, type safety, and contributor credits."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from core import LabDatabase, Column, LabError
from model_ext import insert_data, editable_records, update_record, delete_record
from i18n import tr
from locale_support import error_summary
from version_info import APP_VERSION, QA_LEAD_FA, QA_LEAD_EN


class DatabaseEntrySafetyTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.folder.name)/'release.db')
        self.db.create_table('Parent', [Column('ID','INT',True)])
        self.db.create_table('Child', [Column('ID','INT',True,True,True),
                                     Column('ParentID','INT'),
                                     Column('Name','NVARCHAR(12)',False,True),
                                     Column('Score','DECIMAL(5,2)'),
                                     Column('Flag','BIT')])
        self.db.connect_fields('Parent','ID','Child','ParentID',kind='1:N')
        insert_data(self.db,'Parent',{'ID':1})
    def tearDown(self):
        self.db.close();self.folder.cleanup()
    def test_parent_missing_rejected_on_insert_and_update(self):
        with self.assertRaisesRegex(LabError, 'Foreign key'):
            insert_data(self.db,'Child',{'ParentID':999,'Name':'Ali'})
        insert_data(self.db,'Child',{'ParentID':1,'Name':'Ali'})
        _,_,locators=editable_records(self.db,'Child')
        with self.assertRaisesRegex(LabError, 'Foreign key'):
            update_record(self.db,'Child',locators[0],{'ParentID':999})
        self.assertEqual(self.db.connection.execute('SELECT ParentID FROM Child').fetchone()[0],1)
        self.assertEqual(self.db.check_integrity(),[])
    def test_valid_reparenting_and_parent_delete_protected(self):
        insert_data(self.db,'Parent',{'ID':2})
        insert_data(self.db,'Child',{'ParentID':1,'Name':'Nilo'})
        _,_,locators=editable_records(self.db,'Child')
        update_record(self.db,'Child',locators[0],{'ParentID':'2'})
        self.assertEqual(self.db.connection.execute('SELECT ParentID FROM Child').fetchone()[0],2)
        _,_,ploc=editable_records(self.db,'Parent')
        with self.assertRaises(LabError):
            delete_record(self.db,'Parent',ploc[1])
        self.assertEqual(self.db.check_integrity(),[])
    def test_required_fields_empty_and_null_not_allowed(self):
        for values in ({'ParentID':1}, {'ParentID':1,'Name':''}, {'ParentID':1,'Name':None}):
            with self.subTest(values=values),self.assertRaisesRegex(LabError,'Required field'):
                insert_data(self.db,'Child',values)
        self.assertEqual(self.db.connection.execute('SELECT COUNT(*) FROM Child').fetchone()[0],0)
    def test_type_errors_no_partial_commit(self):
        samples=[
            {'ParentID':'one','Name':'Ali'},
            {'ParentID':1,'Name':'A'*13},
            {'ParentID':1,'Name':'Ali','Score':'oops'},
            {'ParentID':1,'Name':'Ali','Score':'12345.99'},
            {'ParentID':1,'Name':'Ali','Score':'1.234'},
            {'ParentID':1,'Name':'Ali','Flag':'3'},
        ]
        for values in samples:
            with self.subTest(values=values),self.assertRaisesRegex(LabError,'Data type mismatch'):
                insert_data(self.db,'Child',values)
        self.assertEqual(self.db.connection.execute('SELECT count(*) FROM Child').fetchone()[0],0)
    def test_type_mismatch_on_edit_restores_record(self):
        insert_data(self.db,'Child',{'ParentID':1,'Name':'Ali','Flag':1})
        _,_,locators=editable_records(self.db,'Child')
        with self.assertRaisesRegex(LabError,'Data type mismatch'):
            update_record(self.db,'Child',locators[0],{'Flag':'invalid'})
        with self.assertRaisesRegex(LabError,'Required field'):
            update_record(self.db,'Child',locators[0],{'Name':''})
        row=self.db.connection.execute('SELECT Name,Flag FROM Child').fetchone()
        self.assertEqual(tuple(row),('Ali',1))
    def test_identity_cannot_be_manually_inserted_or_updated(self):
        with self.assertRaisesRegex(LabError,'identity'):
            insert_data(self.db,'Child',{'ID':42,'ParentID':1,'Name':'Ali'})
        insert_data(self.db,'Child',{'ParentID':1,'Name':'Ali'})
        _,_,locators=editable_records(self.db,'Child')
        with self.assertRaisesRegex(LabError,'generated'):
            update_record(self.db,'Child',locators[0],{'ID':99})
    def test_no_parent_in_shared_key_one_to_one(self):
        self.db.create_table('Details',[Column('ID','INT',True),Column('Text','NVARCHAR(30)')])
        self.db.connect_fields('Parent','ID','Details','ID',kind='1:1')
        with self.assertRaisesRegex(LabError,'Foreign key'):
            insert_data(self.db,'Details',{'ID':333,'Text':'orphan'})
        insert_data(self.db,'Details',{'ID':1,'Text':'ok'})
        self.assertEqual(self.db.check_integrity(),[])
    def test_junction_both_strategies_guard_each_parent(self):
        self.db.create_table('Course',[Column('ID','INT',True)])
        insert_data(self.db,'Course',{'ID':2})
        for strategy in ('composite','surrogate'):
            name='Bridge'+strategy.title()
            self.db.many_to_many('Parent','Course',name,strategy)
            lookup={fk['table']:fk['from'] for fk in self.db.foreign_keys(name)}
            with self.subTest(strategy=strategy):
                with self.assertRaisesRegex(LabError,'Foreign key'):
                    insert_data(self.db,name,{lookup['Parent']:1,lookup['Course']:404})
                with self.assertRaisesRegex(LabError,'Foreign key'):
                    insert_data(self.db,name,{lookup['Parent']:404,lookup['Course']:2})
                insert_data(self.db,name,{lookup['Parent']:1,lookup['Course']:2})
                self.assertEqual(self.db.check_integrity(),[])
                with self.assertRaises(LabError):
                    insert_data(self.db,name,{lookup['Parent']:1,lookup['Course']:2})
    def test_direct_sql_still_enforces_fk(self):
        with self.assertRaises(Exception):
            self.db.execute("INSERT INTO Child (ParentID,Name) VALUES (555,'Direct SQL')")
        self.assertEqual(self.db.check_integrity(),[])

class CreditsAndMessages(unittest.TestCase):
    def test_credits_in_both_languages_and_current_version(self):
        self.assertEqual(APP_VERSION,'0.8.9')
        self.assertIn('ماهان پاکروان‌نسب',QA_LEAD_FA)
        self.assertIn('Mahan Pakravan-Nasab',QA_LEAD_EN)
        for lang,name in [('fa',QA_LEAD_FA),('en',QA_LEAD_EN)]:
            self.assertIn(name,tr('qa_byline',lang))
            self.assertIn(name,tr('about_text',lang))
            self.assertIn(APP_VERSION,tr('about_text',lang))
    def test_farsi_messages_are_specific(self):
        self.assertIn('کلید خارجی',error_summary(LabError('Foreign key constraint: invalid parent'),'fa'))
        self.assertIn('نوع داده',error_summary(LabError('Data type mismatch'),'fa'))
        self.assertIn('الزامی',error_summary(LabError('Required field: Name'),'fa'))

try:
    from PySide6.QtWidgets import QApplication,QTableWidget
    from PySide6.QtCore import Qt
    from app import MainWindow
    HAS_QT=True
except ImportError:
    HAS_QT=False

@unittest.skipUnless(HAS_QT,'Qt UI tests require PySide6 on a platform runner')
class InlineQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.temp.name)/'qt.db')
        self.db.create_table('Parent',[Column('ID','INT',True)])
        self.db.create_table('Child',[Column('ID','INT',True,True,True),Column('ParentID','INT'),Column('Name','NVARCHAR(20)',False,True)])
        self.db.one_to_many('Parent','Child','ParentID')
        insert_data(self.db,'Parent',{'ID':1})
        self.window=MainWindow()
        self.window.db=self.db
        self.window.refresh_all()
        self.window.show_data('Child')
    def tearDown(self):
        self.window.db=None
        self.window.close()
        self.db.close();self.temp.cleanup()
    def test_inline_insert_tab_and_identity_readonly(self):
        grid=self.window.data_tabs['Child'].findChild(QTableWidget,'dataGrid')
        self.assertTrue(grid.tabKeyNavigation())
        self.assertEqual(grid.rowCount(),1)
        self.assertFalse(bool(grid.item(0,0).flags() & Qt.ItemFlag.ItemIsEditable))
        grid.item(0,1).setText('1')
        grid.item(0,2).setText('Mahan')
        self.window.save_inline_row('Child')
        self.assertEqual(self.db.connection.execute('SELECT Name FROM Child').fetchone()[0],'Mahan')
        grid=self.window.data_tabs['Child'].findChild(QTableWidget,'dataGrid')
        self.assertEqual(grid.rowCount(),2)
        self.assertEqual(grid.currentRow(),1)
    def test_invalid_parent_shows_error_and_preserves_new_row(self):
        grid=self.window.data_tabs['Child'].findChild(QTableWidget,'dataGrid')
        grid.item(0,1).setText('999')
        grid.item(0,2).setText('Mahan')
        with patch('app.error') as report:
            self.window.save_inline_row('Child')
        report.assert_called_once()
        self.assertEqual(self.db.connection.execute('SELECT COUNT(*) FROM Child').fetchone()[0],0)
        self.assertEqual(grid.item(0,1).text(),'999')

if __name__=='__main__':unittest.main()
