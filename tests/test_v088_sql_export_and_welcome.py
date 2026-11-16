"""Release regression: executable T-SQL subset and welcome-title clipping."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from core import LabDatabase, LabError, Column
from model_ext import insert_data
from sqlserver_export import make_script, sqltype
from version_info import APP_VERSION
from i18n import tr


class SqlServerScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=LabDatabase(Path(self.tmp.name)/'sample.db')
        self.db.create_table('ZParent',[Column('ID','INT',True,auto=True,seed=100,increment=5),
                                        Column('Name','NVARCHAR(50)',required=True)])
        self.db.create_table('AChild',[Column('ID','INT',True,auto=True),Column('Title','NVARCHAR(50)')])
        self.db.one_to_many('ZParent','AChild','ParentID',False)
        insert_data(self.db,'ZParent',{'Name':"علی's"})
        insert_data(self.db,'AChild',{'Title':'First','ParentID':100})

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def test_ssms_conventions_fk_identity_unicode_and_order(self):
        sql=make_script(self.db,['AChild','ZParent'],'both','2022','SchoolDB')
        self.assertIn('SQL Server Simulator v'+APP_VERSION,sql)
        self.assertIn('SET ANSI_NULLS ON;',sql)
        self.assertIn('SET QUOTED_IDENTIFIER ON;',sql)
        self.assertIn('CREATE DATABASE [SchoolDB]',sql)
        self.assertIn('USE [SchoolDB]',sql)
        self.assertIn('IDENTITY(100,5)',sql)
        self.assertIn("N'علی''s'",sql)
        self.assertIn('SET IDENTITY_INSERT [dbo].[ZParent] ON;',sql)
        self.assertIn('ALTER TABLE [dbo].[AChild] WITH CHECK ADD CONSTRAINT',sql)
        self.assertLess(sql.index('CREATE TABLE [dbo].[ZParent]'),sql.index('ALTER TABLE [dbo].[AChild]'))
        self.assertLess(sql.index('INSERT INTO [dbo].[AChild]'),sql.index('ALTER TABLE [dbo].[AChild]'))

    def test_data_only_parents_before_children(self):
        sql=make_script(self.db,['AChild','ZParent'],'data','2022')
        self.assertLess(sql.index('INSERT INTO [dbo].[ZParent]'),sql.index('INSERT INTO [dbo].[AChild]'))
        self.assertNotIn('CREATE TABLE ',sql)

    def test_many_to_many_surrogate_unique_pair_is_exported(self):
        self.db.create_table('Course',[Column('ID','INT',True,auto=True)])
        self.db.many_to_many('ZParent','Course','Enrollment','surrogate')
        sql=make_script(self.db,['ZParent','Course','Enrollment'],'both','2022')
        self.assertIn('CREATE TABLE [dbo].[Enrollment]',sql)
        self.assertIn('UNIQUE ([ZParent_ID], [Course_ID])',sql)
        self.assertIn('PRIMARY KEY ([JunctionID])',sql)
        self.assertIn('REFERENCES [dbo].[Course] ([ID])',sql)
        self.assertIn('REFERENCES [dbo].[ZParent] ([ID])',sql)

    def test_many_to_many_composite_primary_key_is_exported(self):
        self.db.create_table('Course',[Column('ID','INT',True,auto=True)])
        self.db.many_to_many('ZParent','Course','Enrollment','composite')
        sql=make_script(self.db,['ZParent','Course','Enrollment'],'schema','2012')
        self.assertIn('PRIMARY KEY ([ZParent_ID], [Course_ID])',sql)
        self.assertNotIn('IDENTITY(',sql.split('CREATE TABLE [dbo].[Enrollment]')[1].split('GO')[0])

    def test_extra_index_is_scripted(self):
        self.db.connection.execute('CREATE INDEX idx_child_title ON AChild(Title)')
        sql=make_script(self.db,['AChild','ZParent'],'schema')
        self.assertIn('CREATE INDEX [idx_child_title] ON [dbo].[AChild] ([Title]);',sql)

    def test_unsafe_schema_is_rejected_not_silently_omitted(self):
        self.db.connection.execute('CREATE TABLE Unsafe (ID INT PRIMARY KEY, Price INT CHECK (Price>0))')
        with self.assertRaisesRegex(LabError,'CHECK'):
            make_script(self.db,['Unsafe'],'schema')

    def test_invalid_sql_server_data_types_fail(self):
        for t in ('NCHAR(MAX)', 'BINARY(MAX)', 'VARBINARY(9000)', 'DECIMAL(40,3)'):
            with self.subTest(t=t):
                with self.assertRaises(LabError):sqltype(t)


class WelcomeSourceRegressionTests(unittest.TestCase):
    def test_short_headings_and_measured_title_height(self):
        w=(ROOT/'src/widgets.py').read_text(encoding='utf8')
        self.assertIn("title_text=tr('welcome_title',lang)",w)
        self.assertIn('title.setMinimumHeight(46)',w)
        self.assertIn('title.setWordWrap(True)',w)
        self.assertIn('card.setMinimumHeight(392)',w)
        self.assertNotIn('card.setMaximumHeight',w)
        self.assertLessEqual(len(tr('welcome_title','fa')),22)
        self.assertIn('QA_LEAD_FA',w)

try:
    from PySide6.QtWidgets import QApplication, QLabel, QFrame
    from widgets import WelcomePanel
    HAS_QT=True
except ImportError:
    HAS_QT=False


@unittest.skipUnless(HAS_QT,'PySide6 is required for Qt rendering tests')
class QtWelcomeRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        cls.qt=QApplication.instance() or QApplication([])

    def test_persian_and_english_title_visible_at_three_sizes(self):
        for language in ('fa','en'):
            widget=WelcomePanel(language,lambda:None,lambda:None,lambda:None)
            for width,height in ((420,480),(600,620),(900,700)):
                widget.resize(width,height);widget.show();self.qt.processEvents()
                title=widget.findChild(QLabel,'welcomeTitle')
                card=widget.findChild(QFrame,'welcomeCard')
                self.assertIsNotNone(title)
                self.assertEqual(title.text(),tr('welcome_title',language))
                self.assertGreaterEqual(title.height(),46)
                self.assertGreaterEqual(card.height(),392)
            widget.close()

if __name__=='__main__':
    unittest.main()
