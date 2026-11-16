"""Regression tests for CRUD + SQL script import (no Qt required)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from core import LabDatabase, LabError, Column
from model_ext import editable_records, insert_data, delete_record, update_record
from sql_script_loader import read_sql_script
from tsql_compat import run_script

class EditAndDeleteRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.temp.name)/'class.db')
        self.db.create_table('Dept',[Column('ID','INT',True,True,True),Column('Name','NVARCHAR(50)',False,True)])
        self.db.create_table('Student',[Column('ID','INT',True,True,True),Column('DeptID','INT')])
        self.db.one_to_many('Dept','Student','DeptID',False)
        insert_data(self.db,'Dept',{'Name':'School'})
        insert_data(self.db,'Student',{'DeptID':1})
    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_update_preserves_identity_and_validates_changes(self):
        _,rows,locators=editable_records(self.db,'Dept')
        self.assertEqual(rows[0][0],1)
        update_record(self.db,'Dept',locators[0],{'Name':'Engineering'})
        updated=self.db.connection.execute('SELECT Name FROM Dept WHERE ID=1').fetchone()[0]
        self.assertEqual(updated,'Engineering')
        with self.assertRaises(LabError):update_record(self.db,'Dept',locators[0],{'Name':'Stale'})
        self.assertEqual(self.db.connection.execute('SELECT Name FROM Dept WHERE ID=1').fetchone()[0],updated)

    def test_cannot_modify_identity(self):
        locator=editable_records(self.db,'Student')[2][0]
        with self.assertRaisesRegex(LabError,'database-generated'):
            update_record(self.db,'Student',locator,{'ID':99})

    def test_delete_rejects_parent_with_child(self):
        parent=editable_records(self.db,'Dept')[2][0]
        with self.assertRaises(LabError):delete_record(self.db,'Dept',parent)
        self.assertEqual(self.db.connection.execute('SELECT count(*) FROM Dept').fetchone()[0],1)
        self.assertEqual(self.db.check_integrity(),[])

    def test_delete_child_then_parent(self):
        delete_record(self.db,'Student',editable_records(self.db,'Student')[2][0])
        delete_record(self.db,'Dept',editable_records(self.db,'Dept')[2][0])
        self.assertEqual(self.db.connection.execute('SELECT count(*) FROM Dept').fetchone()[0],0)

    def test_stale_delete_is_rejected(self):
        locator=editable_records(self.db,'Student')[2][0]
        update_record(self.db,'Student',locator,{'DeptID':None})
        with self.assertRaisesRegex(LabError,'changed or deleted'):
            delete_record(self.db,'Student',locator)

class SQLFileTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory()
    def tearDown(self):self.temp.cleanup()
    def write(self,filename,data):
        path=Path(self.temp.name)/filename
        path.write_bytes(data)
        return path

    def test_utf8_and_utf16_bom(self):
        script='CREATE DATABASE School;\nGO\nUSE School;\nGO\nCREATE TABLE Department (Id INTEGER PRIMARY KEY);'
        for filename,data in [('unicode_utf8.sql',script.encode('utf-8-sig')),
                              ('unicode_utf16.sql',script.encode('utf-16'))]:
            with self.subTest(filename=filename):
                path=self.write(filename,data)
                self.assertEqual(read_sql_script(path),script)

    def test_create_database_tables_relations_from_file(self):
        sql='''CREATE DATABASE School;
GO
USE School;
GO
CREATE TABLE Department (Id INTEGER PRIMARY KEY);
CREATE TABLE Student (Id INTEGER PRIMARY KEY, DepartmentId INTEGER REFERENCES Department(Id));
INSERT INTO Department (Id) VALUES (1);
INSERT INTO Student (Id, DepartmentId) VALUES (3, 1);
'''
        path=self.write('school.sql',sql.encode('utf-8'))
        result=run_script(None,read_sql_script(path),self.temp.name)
        try:
            self.assertIn('Department',result.database.tables())
            self.assertIn('Student',result.database.tables())
            self.assertEqual(len(result.database.foreign_keys('Student')),1)
            self.assertEqual(result.database.check_integrity(),[])
        finally:
            result.database.close()

    def test_sql_server_style_go_identity_and_alter_table_foreign_key(self):
        sql='''CREATE DATABASE School;
GO
USE School;
GO
CREATE TABLE [dbo].[Department] ([ID] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY);
CREATE TABLE [dbo].[Student] ([ID] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY, [DeptID] [int] NULL);
GO
ALTER TABLE [dbo].[Student] WITH CHECK ADD CONSTRAINT [FK_Student_Dept] FOREIGN KEY ([DeptID]) REFERENCES [dbo].[Department] ([ID]);
'''
        p=self.write('school_server.sql',sql.encode('utf-8'))
        result=run_script(None,read_sql_script(p),self.temp.name)
        try:
            self.assertEqual(result.database.tables(),['Department','Student'])
            self.assertEqual(result.database.foreign_keys('Student')[0]['from'],'DeptID')
            with self.assertRaises(LabError):insert_data(result.database,'Student',{'DeptID':999})
            self.assertEqual(result.database.check_integrity(),[])
        finally:result.database.close()

    def test_binary_empty_non_sql_and_oversize_rejected(self):
        for filename,data in [('binary.sql',b'\x00\x01'),('blank.sql',b'  \n'),
                              ('not_sql.exe',b'hello'),('large.sql',b'a'*32)]:
            with self.subTest(filename=filename):
                path=self.write(filename,data)
                with self.assertRaises(LabError):read_sql_script(path,max_bytes=20)

if __name__=='__main__':unittest.main()
