"""Executable educational modules: real views and limited parameterized routines."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from core import LabDatabase, Column, LabError
from tsql_compat import run_script
from tsql_modules import list_modules, views


class ModulesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'training.db'
        self.db=LabDatabase(self.path)
        self.db.create_table('Students',[Column('ID','INT',True,True,True), Column('Name','NVARCHAR(50)',required=True)])

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def execute(self,script):
        return run_script(self.db,script,self.tmp.name)

    def test_sqlite_view_is_executable_and_saved(self):
        self.execute('''CREATE VIEW dbo.vStudents AS SELECT ID, Name FROM dbo.Students;
GO
INSERT INTO Students(Name) VALUES(N'علی');
SELECT * FROM dbo.vStudents;''')
        result=self.execute('SELECT Name FROM dbo.vStudents;')
        self.assertEqual(result.rows,[('علی',)])
        self.assertEqual(views(self.db),['vStudents'])

    def test_invalid_view_rejected_and_not_persisted(self):
        with self.assertRaisesRegex(LabError,'CREATE VIEW'):
            self.execute('CREATE VIEW Bad AS SELECT * FROM NotPresent;')
        self.assertNotIn('Bad',views(self.db))

    def test_procedure_insert_with_bound_named_args(self):
        self.execute('''CREATE PROC dbo.AddStudent @Name NVARCHAR(50) AS
BEGIN
  SET NOCOUNT ON;
  INSERT INTO dbo.Students(Name) VALUES(@Name);
  SELECT ID,Name FROM dbo.Students;
END;
GO''')
        malicious="Sara'); DROP TABLE Students;--"
        self.execute("EXEC dbo.AddStudent @Name=N'Sara';")
        self.execute('EXEC dbo.AddStudent @Name='+"N'"+malicious.replace("'","''")+"'")
        self.assertEqual(self.db.tables(),['Students'])
        self.assertEqual(self.execute('SELECT Name FROM Students ORDER BY ID;').rows,[('Sara',),(malicious,)])

    def test_procedure_persists_across_open(self):
        self.execute('CREATE PROCEDURE CountStudents AS SELECT COUNT(*) AS count_students FROM Students;\nGO')
        self.db.close()
        self.db=LabDatabase(self.path)
        self.assertEqual(self.execute('EXEC dbo.CountStudents;').rows,[(0,)])
        self.assertEqual(list_modules(self.db,'PROCEDURE'),['CountStudents'])

    def test_procedure_execution_is_atomic_on_error(self):
        self.execute('''CREATE PROCEDURE TwoInserts @Name NVARCHAR(50) AS BEGIN
INSERT INTO Students (Name) VALUES(@Name);
INSERT INTO Students (MissingColumn) VALUES(999);
END;
GO''')
        with self.assertRaisesRegex(LabError,'rolled back'):
            self.execute("EXEC TwoInserts N'Rose';")
        self.assertEqual(self.execute('SELECT COUNT(*) FROM Students;').rows,[(0,)])

    def test_scalar_function_in_select_and_reopened(self):
        self.execute('''CREATE FUNCTION dbo.DoubleValue(@x INT) RETURNS INT
AS BEGIN RETURN @x * 2; END;
GO''')
        self.assertEqual(self.execute('SELECT dbo.DoubleValue(10) AS Value;').rows,[(20,)])
        self.db.close()
        self.db=LabDatabase(self.path)
        self.assertEqual(self.execute('SELECT dbo.DoubleValue(15) AS Value;').rows,[(30,)])

    def test_scalar_function_multiple_params(self):
        self.execute('''CREATE FUNCTION dbo.Tax(@price DECIMAL(8,2), @rate DECIMAL(4,2))
RETURNS DECIMAL(10,2) AS BEGIN RETURN ROUND(@price * @rate, 2); END;
GO''')
        self.assertEqual(self.execute('SELECT dbo.Tax(100,0.12);').rows,[(12.0,)])

    def test_scalar_table_valued_rejected(self):
        with self.assertRaisesRegex(LabError,'Scalar|scalar'):
            self.execute('CREATE FUNCTION dbo.TableFunction() RETURNS TABLE AS RETURN SELECT * FROM Students;')

    def test_unsupported_procedure_control_flow_rejected(self):
        with self.assertRaisesRegex(LabError,'IF/WHILE'):
            self.execute('CREATE PROC InvalidProc AS BEGIN IF 1=1 SELECT 1; END;')
        self.assertNotIn('InvalidProc',list_modules(self.db,'PROCEDURE'))

    def test_drop_recreate_view_procedure_function(self):
        self.execute('CREATE VIEW ViewTest AS SELECT ID FROM Students;\nGO')
        self.execute('CREATE PROC SampleProc AS SELECT 1;\nGO')
        self.execute('CREATE FUNCTION SampleFn(@x INT) RETURNS INT AS RETURN @x+1;\nGO')
        self.execute('DROP VIEW ViewTest; DROP PROC SampleProc; DROP FUNCTION SampleFn;')
        self.assertEqual(views(self.db),[])
        self.assertEqual(list_modules(self.db,'PROCEDURE'),[])
        self.assertEqual(list_modules(self.db,'FUNCTION'),[])

    def test_foreign_keys_stay_active_during_proc(self):
        self.db.create_table('Parents',[Column('ID','INT',True,True,True)])
        self.db.create_table('Children',[Column('ID','INT',True,True,True),Column('ParentID','INT')])
        self.db.one_to_many('Parents','Children','ParentID')
        self.execute('CREATE PROC BadChild @ParentID INT AS INSERT INTO Children(ParentID) VALUES(@ParentID);\nGO')
        with self.assertRaises(LabError):self.execute('EXEC BadChild 999;')
        self.assertEqual(self.execute('SELECT COUNT(*) FROM Children;').rows,[(0,)])

    def test_undefined_and_missing_arguments_rejected(self):
        self.execute('CREATE PROC NeedName @Name NVARCHAR(20) AS SELECT @Name;\nGO')
        with self.assertRaisesRegex(LabError,'Missing'):
            self.execute('EXEC NeedName;')
        with self.assertRaisesRegex(LabError,'Unknown'):
            self.execute('EXEC NeedName @Unknown=1;')

    def test_creation_errors_do_not_claim_success(self):
        with self.assertRaisesRegex(LabError,'Unsupported|supported'):
            self.execute('CREATE FUNCTION dbo.Wild(@x INT) RETURNS INT AS BEGIN SELECT @x; RETURN @x; END;')
        self.assertEqual(list_modules(self.db,'FUNCTION'),[])

try:
    from PySide6.QtWidgets import QApplication, QTreeWidgetItem
    from PySide6.QtCore import Qt
    from app import MainWindow
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, 'PySide6 unavailable; Windows/macOS/Linux CI must run this test')
class ModulesQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp=QApplication.instance() or QApplication([])

    def test_object_explorer_lists_views_procedures_and_functions(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'modules.db'
            db=LabDatabase(path)
            db.create_table('T',[Column('ID','INT',True,True,True)])
            run_script(db,'CREATE VIEW vT AS SELECT ID FROM T;\nGO',directory)
            run_script(db,'CREATE PROC ListT AS SELECT ID FROM T;\nGO',directory)
            run_script(db,'CREATE FUNCTION PlusOne(@x INT) RETURNS INT AS RETURN @x+1;\nGO',directory)
            db.close()
            win=MainWindow()
            try:
                win.load_database(path)
                explorer=win.explorer
                labels=[]
                def visit(item):
                    labels.append(item.text(0))
                    for index in range(item.childCount()):visit(item.child(index))
                for index in range(explorer.topLevelItemCount()):visit(explorer.topLevelItem(index))
                for expected in ('Views (1)','Stored Procedures (1)','Scalar Functions (1)',
                                 'vT','ListT','PlusOne'):
                    self.assertIn(expected,labels)
                win.open_module('view','vT')
                self.assertIn('SELECT *',win.editor.toPlainText())
            finally:
                win.close()


if __name__=='__main__':unittest.main()
