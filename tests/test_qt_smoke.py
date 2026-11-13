"""Optional Qt smoke test, run when PySide6-Essentials is available (e.g. Windows builder)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    from PySide6.QtWidgets import QApplication
    from app import MainWindow
    from dialogs import TableDesigner,RelationshipWizard,ScriptExportWizard,GridRowEditor
    from widgets import SQLEditor
    from core import LabDatabase, Column
    from model_ext import is_identity
    HAS_QT=True
except ImportError:
    HAS_QT=False

@unittest.skipUnless(HAS_QT,'PySide6 not available in test environment')
class QtSmokeTests(unittest.TestCase):
    def test_editor_current_line_highlight_and_themes(self):
        app=QApplication.instance() or QApplication([])
        editor=SQLEditor('dark')
        editor.setPlainText('SELECT 1;\nSELECT 2;')
        self.assertEqual(len(editor.extraSelections()), 1)
        editor.set_theme('light')
        self.assertEqual(len(editor.extraSelections()), 1)
        editor.close()

    def test_wizards_type_picker_and_grid(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            db=LabDatabase(Path(folder)/'sample.db')
            db.create_table('Department',[Column('ID','INT',primary=True,auto=True)])
            db.create_table('Student',[Column('StudentID','INT',primary=True,auto=True)])
            designer=TableDesigner(db,'en',lambda:None)
            self.assertEqual(designer.type_combo(1).currentText(),'NVARCHAR(100)')
            self.assertTrue(designer.check(0,4).isChecked())
            relationship=RelationshipWizard(db,'en',lambda:None)
            self.assertGreaterEqual(relationship.pageIds().__len__(),2)
            self.assertIn(relationship.fk.text(),('DepartmentID','StudentID'))
            export=ScriptExportWizard(db,'en')
            self.assertEqual(export.tablelist.count(),2)
            self.assertEqual(export.version.currentData(),'2022')
            edit=GridRowEditor(db,'Student','en',lambda:None)
            self.assertEqual(edit.newrow,0)
            self.assertEqual(edit.grid.columnCount(),1)
            for dialog in (designer,relationship,export,edit):dialog.close()
            db.close()
        del app

    def test_design_existing_table_and_visual_link_controls(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'visual.db'
            db=LabDatabase(path)
            db.create_table('Department',[Column('ID','INT',True,True,True)])
            db.create_table('Employee',[Column('ID','INT',True,True,True),Column('FullName','NVARCHAR(50)')])
            designer=TableDesigner(db,'en',lambda:None,table='Employee')
            self.assertTrue(designer.table_name.isReadOnly())
            self.assertEqual(designer.grid.rowCount(),2)
            self.assertEqual(designer.grid.item(1,0).data(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.ItemDataRole.UserRole),'FullName')
            designer.grid.item(1,0).setText('DisplayName')
            designer.save()
            self.assertEqual(db.columns('Employee')[1]['name'],'DisplayName')
            rel=RelationshipWizard(db,'en',lambda:None,source_table='Department',target_table='Employee')
            self.assertEqual(rel.kind.currentData(),'1:N')
            self.assertEqual(rel.parent_combo.currentText(),'Department')
            self.assertEqual(rel.child_combo.currentText(),'Employee')
            self_ref=RelationshipWizard(db,'en',lambda:None,source_table='Employee',target_table='Employee')
            self.assertEqual(self_ref.kind.currentData(),'SELF')
            self.assertEqual(self_ref.child_combo.currentText(),'Employee')
            window=MainWindow();window.load_database(path)
            self.assertIn('Employee',window.diagram.nodes)
            self.assertTrue(callable(window.diagram.on_design))
            self.assertTrue(callable(window.diagram.on_new_table))
            self.assertTrue(callable(window.diagram.on_connect))
            window.diagram.start_connect(True)
            self.assertTrue(window.diagram.connect_mode)
            window.diagram.start_connect(False)
            self.assertFalse(window.diagram.connect_mode)
            window.close()
            designer.close();rel.close();self_ref.close();db.close()
        del app

    def test_desktop_shell_explorer_diagram_and_data(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'smoke.db'
            db=LabDatabase(path)
            db.create_table('Student',[Column('StudentID','INTEGER',primary=True,auto=True),Column('Name','TEXT')])
            db.close()
            window=MainWindow()
            window.load_database(path)
            self.assertIn('Student',window.db.tables())
            self.assertTrue(is_identity(window.db,'Student','StudentID'))
            self.assertIn('Student',window.diagram.nodes)
            window.show_data('Student')
            self.assertIn('Student',window.data_tabs)
            window.close()
        del app

@unittest.skipUnless(HAS_QT,'PySide6 not available in test environment')
class ColumnDragAndClosingSmoke(unittest.TestCase):
    def test_wizard_maps_exact_picked_fields(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            db=LabDatabase(Path(folder)/'picked.db')
            db.create_table('Dept',[Column('DeptID','INT',True,True,True)])
            db.create_table('Person',[Column('PersonID','INT',True,True,True),Column('DeptID','INT')])
            wizard=RelationshipWizard(db,'en',lambda:None,source_table='Dept',target_table='Person',
                                      source_field='DeptID',target_field='DeptID')
            self.assertEqual(wizard.kind.currentData(),'1:N')
            self.assertEqual(wizard.parent_field.currentText(),'DeptID')
            self.assertEqual(wizard.child_field.currentText(),'DeptID')
            self.assertTrue(wizard.parent_field.count()>0)
            wizard.close();db.close()

    def test_diagram_can_hide_restore_and_close_data_tabs(self):
        from PySide6.QtCore import QPointF
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'closing.db'
            db=LabDatabase(path)
            db.create_table('Dept',[Column('DeptID','INT',True,True,True)])
            db.create_table('Student',[Column('StudentID','INT',True,True,True),Column('DeptID','INT')])
            db.close()
            win=MainWindow();win.load_database(path)
            diagram=win.diagram
            self.assertTrue(callable(diagram.on_field_connect))
            node=diagram.nodes['Student']
            self.assertEqual(node.column_at(node.mapToScene(QPointF(25,90))),'DeptID')
            self.assertTrue(node.close_hit(node.mapToScene(QPointF(245,20))))
            diagram.hide_table('Student')
            self.assertNotIn('Student',diagram.nodes)
            self.assertIn('Student',win.db.tables())
            win.refresh_all()
            self.assertNotIn('Student',diagram.nodes)
            diagram.show_table('Student')
            self.assertIn('Student',diagram.nodes)
            win.show_data('Student')
            ix=win.tabs.indexOf(win.data_tabs['Student'])
            self.assertGreaterEqual(ix,0)
            win.close_data_tab(ix)
            self.assertNotIn('Student',win.data_tabs)
            self.assertIn('Student',win.db.tables())
            win.close()
