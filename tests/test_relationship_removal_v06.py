"""Destructive diagram actions must remove constraints but never remove table data."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import LabDatabase,Column,LabError

class RelationshipRemovalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.temp.name)/'delete.db')
        self.db.create_table('Dept',[Column('ID','INT',True,True,True)])
        self.db.create_table('Student',[Column('ID','INT',True,True,True),Column('DeptID','INT'),Column('AdvisorID','INT')])
        self.db.connection.execute('INSERT INTO Dept DEFAULT VALUES')
        self.db.connection.execute('INSERT INTO Student (DeptID) VALUES (1)')
        self.db.connection.commit()
    def tearDown(self):
        self.db.close();self.temp.cleanup()
    def test_click_link_lookup_and_delete_real_fk_preserves_rows(self):
        db=self.db
        db.connect_fields('Dept','ID','Student','DeptID','1:N')
        link=next(l for l in db.links() if l['parent']=='Dept')
        self.assertEqual(link['fk_id'],0)
        db.remove_relationship(link['child'],link['fk_id'])
        self.assertEqual(db.foreign_keys('Student'),[])
        self.assertEqual(db.connection.execute('SELECT DeptID FROM Student').fetchone()[0],1)
        self.assertEqual(db.connection.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertEqual(db.check_integrity(),[])
        # This used to be blocked and is now intentionally permitted.
        db.connection.execute('UPDATE Student SET DeptID=777')
        db.connection.commit()
        self.assertEqual(db.connection.execute('SELECT DeptID FROM Student').fetchone()[0],777)
        # Identity still works after rebuilding.
        db.connection.execute('INSERT INTO Student (DeptID) VALUES (777)')
        db.connection.commit()
        self.assertEqual(db.connection.execute('SELECT MAX(ID) FROM Student').fetchone()[0],2)

    def test_remove_only_selected_fk_in_multi_fk_child(self):
        db=self.db
        db.create_table('Advisor',[Column('ID','INT',True,True,True)])
        db.connection.execute('INSERT INTO Advisor DEFAULT VALUES')
        db.connection.commit()
        db.connect_fields('Dept','ID','Student','DeptID','1:N')
        db.connect_fields('Advisor','ID','Student','AdvisorID','1:N')
        link=next(l for l in db.links() if l['parent']=='Dept')
        db.remove_relationship(link['child'],link['fk_id'])
        fks=db.foreign_keys('Student')
        self.assertEqual(len(fks),1)
        self.assertEqual(fks[0]['table'],'Advisor')
        with self.assertRaises(sqlite3.IntegrityError):
            db.connection.execute('INSERT INTO Student (AdvisorID) VALUES (989)')
        db.connection.rollback()

    def test_delete_self_reference_preserves_hierarchy_values(self):
        db=self.db
        db.connect_fields('Student','ID','Student','AdvisorID','SELF')
        l=next(l for l in db.links() if l['kind']=='SELF')
        db.remove_relationship(l['child'],l['fk_id'])
        self.assertEqual(db.foreign_keys('Student'),[])
        self.assertEqual(db.connection.execute('SELECT COUNT(*) FROM Student').fetchone()[0],1)

    def test_delete_many_to_many_both_fks_keeps_junction_and_rows(self):
        db=self.db
        db.create_table('Course',[Column('ID','INT',True,True,True)])
        db.connection.execute('INSERT INTO Course DEFAULT VALUES')
        db.connection.commit()
        db.connect_fields('Student','ID','Course','ID','N:M',bridge='Enroll',strategy='composite')
        db.connection.execute('INSERT INTO Enroll (Student_ID,Course_ID) VALUES (1,1)')
        db.connection.commit()
        link=next(l for l in db.links() if l['kind']=='N:M')
        self.assertEqual(link['bridge'],'Enroll')
        db.remove_many_to_many_link('Enroll')
        self.assertEqual(db.foreign_keys('Enroll'),[])
        self.assertIn('Enroll',db.tables())
        self.assertEqual(db.connection.execute('SELECT COUNT(*) FROM Enroll').fetchone()[0],1)
        self.assertFalse(any(l['kind']=='N:M' for l in db.links()))
        self.assertEqual(db.check_integrity(),[])

    def test_invalid_fk_id_refuses_and_has_no_effect(self):
        with self.assertRaisesRegex(LabError,'not found'):
            self.db.remove_relationship('Student',99)
        self.assertEqual(self.db.connection.execute('PRAGMA foreign_keys').fetchone()[0],1)

    def test_unmanaged_custom_index_refuses_and_keeps_fk(self):
        db=self.db
        db.connect_fields('Dept','ID','Student','DeptID','1:N')
        db.connection.execute('CREATE INDEX CustomIndex ON Student (DeptID)')
        db.connection.commit()
        link=next(l for l in db.links() if l['parent']=='Dept')
        with self.assertRaises(LabError):db.remove_relationship('Student',link['fk_id'])
        self.assertEqual(len(db.foreign_keys('Student')),1)
        self.assertEqual(db.connection.execute('SELECT COUNT(*) FROM Student').fetchone()[0],1)

if __name__=='__main__':unittest.main()
