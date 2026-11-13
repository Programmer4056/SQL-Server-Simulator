import sys, unittest, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import LabDatabase,Column,LabError
from model_ext import insert_data

class NewFeatures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.tmp.name)/'db.db')
    def tearDown(self):
        self.db.close(); self.tmp.cleanup()
    def test_custom_identity_and_unicode(self):
        self.db.create_table('Student',[Column('StudentID','INT',True,True,True,100,5),Column('FullName','NVARCHAR(80)',required=True)])
        self.assertEqual(self.db.logical_type('Student','FullName'),'NVARCHAR(80)')
        ids=[]
        for name in ('علی','سارا','آرمان'):
            id,row=insert_data(self.db,'Student',{'FullName':name})
            ids.append(id)
            self.assertEqual(row['StudentID'],id)
        self.assertEqual(ids,[100,105,110])
        self.assertEqual(self.db.columns('Student')[0]['type'],'INTEGER')
        with self.assertRaises(LabError):
            insert_data(self.db,'Student',{'StudentID':888,'FullName':'fail'})
    def test_identity_negative_increment(self):
        self.db.create_table('Neg',[Column('ID','INT',True,auto=True,seed=8,increment=-2)])
        ids=[insert_data(self.db,'Neg',{})[0] for _ in range(3)]
        self.assertEqual(ids,[8,6,4])
    def test_length_check(self):
        self.db.create_table('T',[Column('ID','INTEGER',True,auto=True),Column('Label','NVARCHAR(3)')])
        insert_data(self.db,'T',{'Label':'سه'})
        with self.assertRaises(LabError):insert_data(self.db,'T',{'Label':'long'})
    def test_identity_after_relation_rebuild(self):
        self.db.create_table('P',[Column('ID','INT',True,auto=True)])
        self.db.create_table('C',[Column('ID','INT',True,auto=True,seed=15,increment=3),Column('Name','NVARCHAR(10)')])
        self.db.one_to_many('P','C','P_ID',False)
        self.assertEqual(insert_data(self.db,'C',{'Name':'ok'})[0],15)
if __name__=='__main__': unittest.main()

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.tmp.name)/'project.db')
        self.db.create_table('Department',[Column('ID','INT',True,auto=True,seed=100,increment=5),Column('Title','NVARCHAR(50)',required=True)])
        self.db.create_table('Student',[Column('StudentID','INT',True,auto=True),Column('Name','NVARCHAR(80)',required=True)])
        self.db.one_to_many('Department','Student','DepartmentID',False)
        insert_data(self.db,'Department',{'Title':"کتابخانه's"})
        insert_data(self.db,'Student',{'Name':'علی','DepartmentID':100})
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def test_script_schema_data_custom_identity_unicode(self):
        from sqlserver_export import make_script
        text=make_script(self.db,['Student','Department'],'both','2019','StudyDB')
        self.assertIn('IDENTITY(100,5)',text)
        self.assertIn('NVARCHAR(80)',text)
        self.assertIn('N\'کتابخانه\'\'s\'',text)
        self.assertIn('SET IDENTITY_INSERT [dbo].[Department] ON;',text)
        self.assertIn('FOREIGN KEY ([DepartmentID]) REFERENCES [dbo].[Department] ([ID])',text)
        self.assertIn('CREATE DATABASE [StudyDB]',text)
        self.assertNotIn('CREATE TABLE "__lab_',text)
    def test_script_subset_omits_reference(self):
        from sqlserver_export import make_script
        text=make_script(self.db,['Student'],'schema','2012')
        self.assertIn('CREATE TABLE [dbo].[Student]',text)
        self.assertNotIn('CREATE TABLE [dbo].[Department]',text)
        self.assertIn('omitted: parent table was not selected',text)
    def test_script_data_only_and_file(self):
        from sqlserver_export import make_script,export_script
        result=make_script(self.db,['Department'],'data','2022')
        self.assertNotIn('CREATE TABLE [dbo].[Department]',result)
        self.assertIn('INSERT INTO [dbo].[Department]',result)
        output=Path(self.tmp.name)/'test.sql'
        export_script(self.db,output,['Department'],'both','2022')
        self.assertTrue(output.read_bytes().startswith(b'\xef\xbb\xbf'))
    def test_invalid_scope_rejected(self):
        from sqlserver_export import make_script
        with self.assertRaises(LabError):make_script(self.db,['Absent'],'both','2022')
        with self.assertRaises(LabError):make_script(self.db,['Department'],'all','2022')
    def test_wrong_one_to_many_shared_key_rejected(self):
        self.db.create_table('Invalid',[Column('ID','INT',True,auto=True)])
        with self.assertRaises(LabError):self.db.one_to_many('Department','Invalid','ID')

class PopulatedRelationshipTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.tmp.name)/'many.db')
        self.db.create_table('Parent',[Column('ID','INT',True,auto=True)])
        self.db.create_table('Child',[Column('ID','INT',True,auto=True,seed=10,increment=2),Column('ParentID','INT'),Column('Title','NVARCHAR(20)')])
        insert_data(self.db,'Parent',{})
        insert_data(self.db,'Child',{'ParentID':1,'Title':'سلام'})
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def test_migrate_existing_child_rows_safely(self):
        self.db.one_to_many('Parent','Child','ParentID',False)
        self.assertEqual(self.db.foreign_keys('Child')[0]['table'],'Parent')
        rows=self.db.connection.execute('SELECT ID, ParentID, Title FROM Child').fetchall()
        self.assertEqual([tuple(x) for x in rows],[(10,1,'سلام')])
        self.assertEqual(insert_data(self.db,'Child',{'ParentID':1,'Title':'two'})[0],12)
    def test_orphan_is_rejected_without_losing_rows(self):
        self.db.connection.execute('UPDATE Child SET ParentID=999')
        self.db.connection.commit()
        with self.assertRaises(LabError):self.db.one_to_many('Parent','Child','ParentID',False)
        self.assertEqual(self.db.connection.execute('SELECT COUNT(*) FROM Child').fetchone()[0],1)
        self.assertEqual(len(self.db.foreign_keys('Child')),0)
    def test_new_nullable_fk_preserves_rows(self):
        self.db.one_to_many('Parent','Child','NewParentID',False)
        row=self.db.connection.execute('SELECT ID,Title,NewParentID FROM Child').fetchone()
        self.assertEqual(tuple(row),(10,'سلام',None))
    def test_new_required_fk_rejected_on_populated_child(self):
        with self.assertRaises(LabError):self.db.one_to_many('Parent','Child','NewParentID',True)
        self.assertEqual(len(self.db.columns('Child')),3)
