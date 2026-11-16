"""Release 0.7 regressions: T-SQL educational subset, schema safety and layout."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import LabDatabase, Column, LabError
from layout_engine import auto_layout
from model_ext import get_rows, insert_data
from tsql_compat import run_script, split_batches

class TsqlCompatibility(unittest.TestCase):
    def test_create_use_go_create_table_identity_and_metadata_security(self):
        with tempfile.TemporaryDirectory() as dirname:
            script='''CREATE DATABASE Training;
GO
USE Training;
GO
CREATE TABLE [dbo].[Students] (
  [StudentID] INT IDENTITY(100,5) PRIMARY KEY,
  [Name] NVARCHAR(50) NOT NULL
);
GO
CREATE USER student WITHOUT LOGIN;
GRANT SELECT, INSERT ON dbo.Students TO student;
DENY DELETE ON [dbo].[Students] TO student;'''
            result=run_script(None,script,dirname)
            db=result.database
            self.assertEqual(db.path.name,'Training.db')
            self.assertEqual(db.tables(),['Students'])
            self.assertIn('NOT ENFORCED',result.messages)
            self.assertEqual(db.connection.execute('SELECT COUNT(*) FROM __lab_permissions').fetchone()[0],3)
            rows=[insert_data(db,'Students',{'Name':n})[0] for n in ('Ali','Sara','Tina')]
            self.assertEqual(rows,[100,105,110])
            db.close()

    def test_use_missing_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as dirname:
            with self.assertRaisesRegex(LabError,'not found'):
                run_script(None,'USE Absent\nGO',dirname)
            self.assertEqual(list(Path(dirname).iterdir()),[])

    def test_security_does_not_pretend_to_enforce_permissions(self):
        with tempfile.TemporaryDirectory() as dirname:
            db=LabDatabase(Path(dirname)/'a.db')
            db.create_table('T',[Column('ID','INT',True,True,True)])
            result=run_script(db,'CREATE USER alice; GRANT SELECT ON dbo.T TO alice; DENY UPDATE ON T TO alice;',dirname)
            self.assertIn('SIMULATED',result.messages)
            self.assertIn('NOT ENFORCED',result.messages)
            self.assertEqual(db.connection.execute('SELECT decision FROM __lab_permissions WHERE operation="UPDATE"').fetchone()[0],'DENY')
            db.close()

    def test_complete_sample_script_with_comments_and_unicode(self):
        sample=Path(__file__).resolve().parents[1]/'examples/TSQL_Teaching_v0_7.sql'
        with tempfile.TemporaryDirectory() as dirname:
            result=run_script(None,sample.read_text(encoding='utf-8'),dirname)
            self.assertEqual(result.rows,[(100,'Ali'),(105,'Sara')])
            self.assertIn('SIMULATED DENY',result.messages)
            result.database.close()

    def test_go_inside_string_does_not_split(self):
        batches=split_batches("SELECT 'hi\\nGO' AS x;\nGO\nSELECT 2;")
        self.assertEqual(len(batches),2)
        self.assertIn("GO'",batches[0])

    def test_unsupported_security_operation_is_explicit(self):
        with tempfile.TemporaryDirectory() as dirname:
            db=LabDatabase(Path(dirname)/'x.db')
            with self.assertRaisesRegex(LabError,'not implemented'):
                run_script(db,'CREATE LOGIN dangerous WITH PASSWORD = \'x\';',dirname)
            self.assertEqual(db.tables(),[])
            db.close()

class SchemaSafety(unittest.TestCase):
    def test_drop_table_referenced_blocked_and_preserves_data(self):
        with tempfile.TemporaryDirectory() as dirname:
            db=LabDatabase(Path(dirname)/'x.db')
            db.create_table('Parent',[Column('ID','INT',True,True,True)])
            db.create_table('Child',[Column('ID','INT',True,True,True),Column('ParentID','INT')])
            db.one_to_many('Parent','Child','ParentID',required=False)
            insert_data(db,'Parent',{})
            insert_data(db,'Child',{'ParentID':1})
            with self.assertRaisesRegex(LabError,'referenced by'):
                db.drop_table('Parent')
            self.assertEqual(db.connection.execute('SELECT COUNT(*) FROM Parent').fetchone()[0],1)
            fk_id=db.foreign_keys('Child')[0]['id']
            db.remove_relationship('Child',fk_id)
            db.drop_table('Parent')
            self.assertNotIn('Parent',db.tables())
            db.close()

    def test_drop_column_preserves_other_values(self):
        with tempfile.TemporaryDirectory() as dirname:
            db=LabDatabase(Path(dirname)/'x.db')
            db.create_table('T',[Column('ID','INT',True,True,True),Column('Temp','NVARCHAR(12)'),Column('Name','NVARCHAR(12)')])
            insert_data(db,'T',{'Name':'Ali','Temp':'Remove'})
            db.drop_column('T','Temp')
            names,rows=get_rows(db,'T')
            self.assertEqual(names,['ID','Name']);self.assertEqual(rows,[(1,'Ali')])
            with self.assertRaises(LabError):db.drop_column('T','ID')
            db.close()

    def test_missing_table_after_external_drop_is_caught(self):
        with tempfile.TemporaryDirectory() as dirname:
            db=LabDatabase(Path(dirname)/'x.db')
            db.create_table('audit_logs',[Column('ID','INT',True,True,True)])
            db.connection.execute('DROP TABLE audit_logs');db.connection.commit()
            with self.assertRaisesRegex(LabError,'not exist'):
                get_rows(db,'audit_logs')
            db.reconcile_schema()
            self.assertEqual(db.tables(),[])
            db.close()

    def test_drop_sql_via_compat_should_refuse_fk_violation(self):
        with tempfile.TemporaryDirectory() as dirname:
            db=LabDatabase(Path(dirname)/'x.db')
            db.create_table('P',[Column('ID','INT',True,True,True)])
            db.create_table('C',[Column('ID','INT',True,True,True),Column('PId','INT')])
            db.one_to_many('P','C','PId')
            with self.assertRaisesRegex(LabError,'referenced'):
                run_script(db,'DROP TABLE P;',dirname)
            db.close()

class LayoutTests(unittest.TestCase):
    def test_high_degree_hub_and_disconnected(self):
        links=[{'parent':'Hub','child':n} for n in ('A','B','C','D','E')]
        names=['Hub','A','B','C','D','E','Isolated']
        positions=auto_layout(names,links)
        self.assertEqual(set(positions),set(names))
        self.assertEqual(len(positions),len(set(positions.values())))
        self.assertEqual(positions,auto_layout(names,links))
        from math import hypot
        # Node centers must have enough distance to avoid ~254x~200 cards.
        for i,name in enumerate(names):
            for other in names[i+1:]:
                a=positions[name];b=positions[other]
                self.assertGreaterEqual(hypot(a[0]-b[0],a[1]-b[1]),290)

if __name__=='__main__':unittest.main()
