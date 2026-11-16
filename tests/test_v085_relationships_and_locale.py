"""Regression tests for v0.8.5 relational key choices and error localization."""
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import LabDatabase, Column, LabError
from model_ext import insert_data, editable_records, update_record
from locale_support import error_summary, runtime_message
from sqlserver_export import make_script

class RelationshipTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.tmp.name)/'lesson.db')
        self.db.create_table('Department',[Column('ID','INT',True)])
        self.db.create_table('Student',[Column('ID','INT',True),Column('DepartmentID','INT')])
        self.db.connection.execute('INSERT INTO Department VALUES (1)')
        self.db.connection.commit()
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def test_one_many_independent_pk(self):
        self.db.connect_fields('Department','ID','Student','DepartmentID',kind='1:N')
        self.assertEqual([c['name'] for c in self.db.columns('Student') if c['pk']],['ID'])
        insert_data(self.db,'Student',{'ID':11,'DepartmentID':1})
        with self.assertRaises(LabError):insert_data(self.db,'Student',{'ID':12,'DepartmentID':999})
    def test_one_many_composite_pk(self):
        self.db.connect_fields('Department','ID','Student','DepartmentID',kind='1:N',composite_child_pk=True)
        self.assertEqual([c['name'] for c in self.db.columns('Student') if c['pk']],['ID','DepartmentID'])
        self.assertEqual(self.db.foreign_keys('Student')[0]['table'],'Department')
        insert_data(self.db,'Student',{'ID':11,'DepartmentID':1})
        with self.assertRaises(LabError):insert_data(self.db,'Student',{'ID':11,'DepartmentID':1})
        with self.assertRaises(LabError):insert_data(self.db,'Student',{'ID':12,'DepartmentID':9})
        with self.assertRaises(LabError):insert_data(self.db,'Student',{'ID':13,'DepartmentID':None})
    def test_composite_fk_refuses_identity_child(self):
        self.db.create_table('Badge',[Column('ID','INT',True,True,True),Column('DepartmentID','INT')])
        with self.assertRaisesRegex(LabError,'IDENTITY'):
            self.db.connect_fields('Department','ID','Badge','DepartmentID',kind='1:N',composite_child_pk=True)
        self.assertEqual(self.db.foreign_keys('Badge'),[])
    def test_composite_existing_orphan_rolls_back(self):
        insert_data(self.db,'Student',{'ID':10,'DepartmentID':999})
        with self.assertRaises(LabError):
            self.db.connect_fields('Department','ID','Student','DepartmentID',kind='1:N',composite_child_pk=True)
        self.assertEqual(self.db.foreign_keys('Student'),[])
        self.assertEqual(self.db.connection.execute('SELECT COUNT(*) FROM Student').fetchone()[0],1)
    def test_nm_both_strategies_enforce_fks_and_pairs(self):
        self.db.create_table('Course',[Column('CourseID','INT',True)])
        self.db.connection.execute('INSERT INTO Course VALUES(10)')
        self.db.connection.commit()
        for name,strategy in [('EnrollComposite','composite'),('EnrollIdentity','surrogate')]:
            self.db.many_to_many('Department','Course',name,strategy)
            self.assertEqual(len(self.db.foreign_keys(name)),2)
            fk=self.db.foreign_keys(name)
            cols=[row['from'] for row in fk]
            insert_data(self.db,name,dict(zip(cols,[10 if 'Course' in c else 1 for c in cols])))
            with self.assertRaises(LabError):
                insert_data(self.db,name,dict(zip(cols,[10 if 'Course' in c else 1 for c in cols])))
            with self.assertRaises(LabError):
                insert_data(self.db,name,dict(zip(cols,[999 if 'Course' in c else 1 for c in cols])))
            keys=[c['name'] for c in self.db.columns(name) if c['pk']]
            self.assertEqual(len(keys),2 if strategy=='composite' else 1)
    def test_script_composite_key_exported(self):
        self.db.connect_fields('Department','ID','Student','DepartmentID',kind='1:N',composite_child_pk=True)
        script=make_script(self.db,['Department','Student'],'schema','2022')
        self.assertIn('PRIMARY KEY',script.upper())
        self.assertIn('FOREIGN KEY',script.upper())
    def test_inline_model_enforces_identity_immutability(self):
        self.db.create_table('Generated',[Column('ID','INT',True,True,True),Column('Name','NVARCHAR(20)')])
        insert_data(self.db,'Generated',{'Name':'Ali'})
        names,rows,locators=editable_records(self.db,'Generated')
        update_record(self.db,'Generated',locators[0],{'Name':'Sara'})
        self.assertEqual(self.db.connection.execute('SELECT Name FROM Generated').fetchone()[0],'Sara')
        with self.assertRaisesRegex(LabError,'generated'):
            update_record(self.db,'Generated',locators[0],{'ID':100})

class LocalizationTests(unittest.TestCase):
    def test_fk_error_farsi(self):
        self.assertIn('کلید خارجی',error_summary(ValueError('FOREIGN KEY constraint failed'),'fa'))
    def test_identity_error_farsi(self):
        self.assertIn('خودکار',error_summary(ValueError('ID is database-generated and cannot be changed manually.'),'fa'))
    def test_delete_confirmation_farsi(self):
        self.assertIn('حذف دائمی',runtime_message('Permanently delete the selected row? This cannot be undone.','fa'))

if __name__=='__main__':unittest.main()
