import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core import LabDatabase, LabError, Column
from model_ext import insert_data, get_rows, is_identity

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = LabDatabase(Path(self.temp.name) / 'sample.db')
    def tearDown(self):
        self.db.close()
        self.temp.cleanup()
    def test_generated_identity_in_table_designer_and_form(self):
        self.db.create_table('Products', [Column('ProductID', 'INTEGER', primary=True, auto=True), Column('Name', 'TEXT', required=True)])
        self.assertTrue(is_identity(self.db, 'Products', 'ProductID'))
        self.assertFalse(is_identity(self.db, 'Products', 'Name'))
        first, row = insert_data(self.db, 'Products', {'Name':'Monitor'})
        second, row2 = insert_data(self.db, 'Products', {'Name':'Mouse'})
        self.assertEqual((first,second), (1,2))
        self.assertEqual([r[0] for r in get_rows(self.db,'Products')[1]], [1,2])
        self.assertEqual(row['ProductID'], 1)
        self.assertEqual(row2['ProductID'], 2)
        with self.assertRaises(LabError):
            insert_data(self.db, 'Products', {'ProductID':100,'Name':'Invalid'})
    def test_db_checks_not_null_and_fk_even_without_query(self):
        self.db.create_table('Parent', [Column('ParentID','INTEGER',primary=True,auto=True)])
        self.db.create_table('Child', [Column('ChildID','INTEGER',primary=True,auto=True), Column('Title','TEXT',required=True)])
        self.db.one_to_many('Parent','Child','ParentID',required=True)
        with self.assertRaises(LabError):
            insert_data(self.db,'Child',{'Title':'orphan','ParentID':99})
        with self.assertRaises(LabError):
            insert_data(self.db,'Child',{'ParentID':1})
        pid,_=insert_data(self.db,'Parent',{})
        cid,record=insert_data(self.db,'Child',{'ParentID':pid,'Title':'ok'})
        self.assertEqual((cid, record['ParentID']), (1,1))
    def test_junction_auto_generated(self):
        for n in ['Student','Course']:
            self.db.create_table(n,[Column('ID','INTEGER',primary=True,auto=True)])
        self.db.many_to_many('Student','Course','Enroll','surrogate')
        self.assertTrue(is_identity(self.db,'Enroll','JunctionID'))
        insert_data(self.db,'Student',{})
        insert_data(self.db,'Course',{})
        insert_data(self.db,'Enroll',{'Student_ID':1,'Course_ID':1})
        with self.assertRaises(LabError):
            insert_data(self.db,'Enroll',{'Student_ID':1,'Course_ID':1})
    def test_manual_pk_remains_manual(self):
        self.db.create_table('Codes',[Column('Code','TEXT',primary=True),Column('Title','TEXT')])
        self.assertFalse(is_identity(self.db,'Codes','Code'))
        rid,row=insert_data(self.db,'Codes',{'Code':'A1','Title':'Hello'})
        self.assertEqual(row['Code'],'A1')
if __name__=='__main__': unittest.main()
