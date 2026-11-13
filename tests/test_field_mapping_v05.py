"""Regression checks for v0.5 column-to-column wizard and enforced FK rules."""
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import LabDatabase,Column,LabError

class FieldMappingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.tmp.name)/'mapping.db')
        self.db.create_table('Department',[
            Column('DepartmentID','INT',True,True,True),
            Column('Title','NVARCHAR(50)')])
        self.db.create_table('Student',[
            Column('StudentID','INT',True,True,True),
            Column('DepartmentID','INT'),
            Column('StudentName','NVARCHAR(50)')])
        self.db.connection.execute('INSERT INTO Department (Title) VALUES (?)',('Engineering',))
        self.db.connection.commit()
    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def test_valid_existing_field_fk_enforced_after_connection(self):
        self.db.connection.execute('INSERT INTO Student (DepartmentID,StudentName) VALUES (1,?)',('Ali',))
        self.db.connection.commit()
        self.db.connect_fields('Department','DepartmentID','Student','DepartmentID','1:N')
        self.assertEqual(self.db.foreign_keys('Student')[0]['table'],'Department')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.connection.execute('INSERT INTO Student (DepartmentID,StudentName) VALUES (99,?)',('invalid',))
        self.db.connection.rollback()
        self.assertEqual(self.db.check_integrity(),[])

    def test_rejects_orphan_child_before_rebuild(self):
        self.db.connection.execute('INSERT INTO Student (DepartmentID) VALUES (98)')
        self.db.connection.commit()
        before=self.db.connection.execute('SELECT DepartmentID FROM Student').fetchone()[0]
        with self.assertRaisesRegex(LabError,'Referential integrity'):
            self.db.connect_fields('Department','DepartmentID','Student','DepartmentID','1:N')
        self.assertEqual(self.db.foreign_keys('Student'),[])
        self.assertEqual(self.db.connection.execute('SELECT DepartmentID FROM Student').fetchone()[0],before)

    def test_wrong_parent_field_cannot_be_linked(self):
        with self.assertRaisesRegex(LabError,'primary key'):
            self.db.connect_fields('Department','Title','Student','DepartmentID','1:N')

    def test_wrong_type_cannot_be_linked(self):
        with self.assertRaisesRegex(LabError,'Data type mismatch'):
            self.db.connect_fields('Department','DepartmentID','Student','StudentName','1:N')

    def test_required_with_existing_null_rejected(self):
        self.db.connection.execute('INSERT INTO Student (StudentName) VALUES (?)',('Empty',))
        self.db.connection.commit()
        with self.assertRaisesRegex(LabError,'contains NULL'):
            self.db.connect_fields('Department','DepartmentID','Student','DepartmentID','1:N',True)

    def test_optional_null_stays_allowed(self):
        self.db.connection.execute('INSERT INTO Student (StudentName) VALUES (?)',('Empty',))
        self.db.connection.commit()
        self.db.connect_fields('Department','DepartmentID','Student','DepartmentID','1:N',False)
        self.assertEqual(self.db.connection.execute('SELECT DepartmentID FROM Student').fetchone()[0],None)

    def test_create_new_optional_fk_on_populated_child(self):
        self.db.connection.execute('INSERT INTO Student (StudentName) VALUES (?)',('Existing',))
        self.db.connection.commit()
        self.db.connect_fields('Department','DepartmentID','Student','NewDeptID','1:N',False)
        self.assertIn('NewDeptID',[c['name'] for c in self.db.columns('Student')])
        self.assertEqual(self.db.connection.execute('SELECT StudentName FROM Student').fetchone()[0],'Existing')

    def test_new_required_column_rejected_without_data_loss(self):
        self.db.connection.execute('INSERT INTO Student (StudentName) VALUES (?)',('Existing',))
        self.db.connection.commit()
        with self.assertRaisesRegex(LabError,'new required FK'):
            self.db.connect_fields('Department','DepartmentID','Student','NewDeptID','1:N',True)
        self.assertNotIn('NewDeptID',[c['name'] for c in self.db.columns('Student')])

    def test_shared_primary_key_requires_identity_off(self):
        self.db.create_table('StudentProfile',[Column('StudentID','INT',True,True,True)])
        with self.assertRaisesRegex(LabError,'Turn off Identity'):
            self.db.connect_fields('Student','StudentID','StudentProfile','StudentID','1:1')
        self.db.create_table('StudentAddress',[Column('StudentID','INT',True,True,False)])
        self.db.connect_fields('Student','StudentID','StudentAddress','StudentID','1:1')
        self.assertEqual(self.db.foreign_keys('StudentAddress')[0]['table'],'Student')

    def test_self_referencing_field_and_orphan_rejected(self):
        self.db.create_table('Staff',[
            Column('ID','INT',True,True,True),Column('ManagerID','INT')])
        self.db.connection.execute('INSERT INTO Staff (ManagerID) VALUES (99)')
        self.db.connection.commit()
        with self.assertRaisesRegex(LabError,'Referential integrity'):
            self.db.connect_fields('Staff','ID','Staff','ManagerID','SELF')
        self.db.connection.execute('UPDATE Staff SET ManagerID=NULL')
        self.db.connection.commit()
        self.db.connect_fields('Staff','ID','Staff','ManagerID','SELF')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.connection.execute('UPDATE Staff SET ManagerID=99')
        self.db.connection.rollback()

    def test_many_to_many_is_real_junction(self):
        self.db.create_table('Course',[Column('CourseID','INT',True,True,True)])
        self.db.connect_fields('Student','StudentID','Course','CourseID','N:M',bridge='Enrollment',strategy='composite')
        bridge=self.db.foreign_keys('Enrollment')
        self.assertEqual({f['table'] for f in bridge},{'Student','Course'})
        self.assertEqual(len([c for c in self.db.columns('Enrollment') if c['pk']]),2)

if __name__=='__main__':unittest.main()
