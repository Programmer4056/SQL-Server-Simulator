"""Regression tests for no-code table design and referential-integrity enforcement."""
import sys
import tempfile
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import LabDatabase,Column,LabError

class VisualDesignTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.tmp.name)/'database.db')
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def basic(self):
        self.db.create_table('Department',[Column('ID','INT',True,True,True),Column('Title','NVARCHAR(50)')])
        self.db.create_table('Student',[Column('ID','INT',True,True,True),Column('Name','NVARCHAR(50)')])
        self.db.one_to_many('Department','Student','DepartmentID',False)
        self.db.execute("INSERT INTO Department(Title) VALUES ('IT'); INSERT INTO Student(Name,DepartmentID) VALUES('Ali',1)")
    def test_design_renames_and_adds_columns_without_erasing_rows(self):
        self.basic()
        cols=[Column('ID','INT',True,True,True),Column('FullName','NVARCHAR(60)'),
              Column('DepartmentID','INT'),Column('Age','INT')]
        self.db.edit_table('Student',cols,{'ID':'ID','FullName':'Name','DepartmentID':'DepartmentID','Age':None})
        self.assertEqual(self.db.execute('SELECT FullName,Age,DepartmentID FROM Student')[1],[('Ali',None,1)])
        self.assertEqual(self.db.foreign_keys('Student')[0]['table'],'Department')
        with self.assertRaises(LabError):
            self.db.execute("INSERT INTO Student(FullName,DepartmentID) VALUES ('Invalid',999)")
        self.assertEqual(self.db.connection.execute('PRAGMA foreign_keys').fetchone()[0],1)
    def test_invalid_existing_data_rolls_back_schema(self):
        self.basic()
        with self.assertRaises(LabError):
            self.db.edit_table('Student',[Column('ID','INT',True,True,True),Column('Name','NVARCHAR(2)'),
                                          Column('DepartmentID','INT')])
        self.assertEqual(self.db.logical_type('Student','Name'),'NVARCHAR(50)')
        self.assertEqual(self.db.execute('SELECT Name FROM Student')[1],[('Ali',)])
        self.assertEqual(self.db.connection.execute('PRAGMA foreign_keys').fetchone()[0],1)
    def test_incoming_referenced_primary_key_protected(self):
        self.basic()
        with self.assertRaises(LabError):
            self.db.edit_table('Department',[Column('DeptKey','INT',True,True,True),Column('Title','NVARCHAR(50)')],
                               {'DeptKey':'ID','Title':'Title'})
        self.assertIn('ID',[c['name'] for c in self.db.columns('Department')])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM Student')[1],[(1,)])
    def test_prevent_deleting_fk_column(self):
        self.basic()
        with self.assertRaises(LabError):
            self.db.edit_table('Student',[Column('ID','INT',True,True,True),Column('Name','NVARCHAR(50)')])
        self.assertEqual(len(self.db.foreign_keys('Student')),1)
    def test_self_reference_can_have_root_and_child(self):
        self.db.create_table('Employee',[Column('EmployeeID','INT',True,True,True),Column('Name','NVARCHAR(50)')])
        self.db.self_reference('Employee','ManagerID')
        self.assertEqual(self.db.links()[0]['kind'],'SELF')
        self.db.execute("INSERT INTO Employee(Name) VALUES('Boss'); INSERT INTO Employee(Name,ManagerID) VALUES('Intern',1)")
        with self.assertRaises(LabError):self.db.execute("INSERT INTO Employee(Name,ManagerID) VALUES('Ghost',900)")
        with self.assertRaises(LabError):self.db.execute('UPDATE Employee SET ManagerID=900 WHERE EmployeeID=2')
        with self.assertRaises(LabError):self.db.execute('DELETE FROM Employee WHERE EmployeeID=1')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM Employee')[1],[(2,)])
    def test_self_reference_existing_columns_and_preserves_rows(self):
        self.db.create_table('Category',[Column('ID','INT',True,True,True),Column('ParentID','INT')])
        self.db.execute('INSERT INTO Category(ID) VALUES(1)')
        self.db.self_reference('Category','ParentID')
        self.db.execute('INSERT INTO Category(ID,ParentID) VALUES(2,1)')
        with self.assertRaises(LabError):self.db.execute('INSERT INTO Category(ID,ParentID) VALUES(3,99)')
    def test_bridge_composite_and_surrogate_edit_preserve_constraints(self):
        for tb in ('Student','Course'):
            self.db.create_table(tb,[Column('ID','INT',True,True,True)])
        self.db.many_to_many('Student','Course','Enrollment','surrogate')
        col=self.db.design_columns('Enrollment')+[Column('Grade','INT')]
        self.db.edit_table('Enrollment',col)
        self.assertEqual(len(self.db.foreign_keys('Enrollment')),2)
        self.db.execute('INSERT INTO Student DEFAULT VALUES; INSERT INTO Course DEFAULT VALUES;')
        self.db.execute('INSERT INTO Enrollment(Student_ID,Course_ID) VALUES(1,1)')
        with self.assertRaises(LabError):
            self.db.execute('INSERT INTO Enrollment(Student_ID,Course_ID) VALUES(1,1)')
        self.assertTrue(any(x['kind']=='N:M' for x in self.db.links()))
    def test_composite_bridge_preserved(self):
        for tb in ('Student','Course'):
            self.db.create_table(tb,[Column('ID','INT',True,True,True)])
        self.db.many_to_many('Student','Course','Enroll','composite')
        self.db.edit_table('Enroll',self.db.design_columns('Enroll')+[Column('Date','DATE')])
        self.assertEqual(sum(bool(c['pk']) for c in self.db.columns('Enroll')),2)
    def test_identity_counter_survives_redesign(self):
        self.db.create_table('OrderItem',[Column('ID','INT',True,True,True,100,5),Column('Title','NVARCHAR(30)')])
        self.db.execute("INSERT INTO OrderItem(Title) VALUES('One')")
        self.db.edit_table('OrderItem',self.db.design_columns('OrderItem')+[Column('Note','NVARCHAR(20)')])
        self.db.execute("INSERT INTO OrderItem(Title) VALUES('Two')")
        self.assertEqual(self.db.execute('SELECT ID FROM OrderItem ORDER BY ID')[1],[(100,),(105,)])
    def test_sql_editor_cannot_disable_fk_validation(self):
        self.basic()
        with self.assertRaises(LabError):self.db.execute('PRAGMA foreign_keys=OFF')
        self.assertEqual(self.db.connection.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertEqual(self.db.check_integrity(),[])
    def test_not_null_column_populated_table_rejected(self):
        self.basic()
        with self.assertRaises(LabError):
            self.db.edit_table('Student',self.db.design_columns('Student')+[Column('Required','INT',required=True)])
        self.assertNotIn('Required',[c['name'] for c in self.db.columns('Student')])

if __name__=='__main__':unittest.main()
