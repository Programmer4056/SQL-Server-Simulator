"""Regression coverage for the Persian Database Diagram UI and welcome layout."""
import os
import sys
import unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from locale_support import ui
from i18n import tr
from version_info import APP_VERSION

class PersianTextTests(unittest.TestCase):
    def test_diagram_context_menu_labels_are_translated(self):
        keys=(
            'Relationship: ', 'Delete Relationship…',
            '×  Close table in diagram (hide only)', 'Design Table  ✎',
            'New Relationship from {table}…', 'Self-referencing relationship…',
            'Reopen hidden table…', 'Show all hidden tables',
            'New Table…', 'Relationship Wizard…',
            'Draw Link (click parent PK, then child FK)', 'Cancel link mode',
        )
        for key in keys:
            self.assertNotEqual(ui(key,'fa'),key,key)
            self.assertEqual(ui(key,'en'),key)
        self.assertIn('Staff',ui('New Relationship from {table}…','fa').format(table='Staff'))

    def test_localized_hints_and_credits(self):
        for key in ('Step 1/2: click the first field (parent PK or child FK).',
                    'Click to select; right-click to remove relationship.',
                    'Drag a column onto another column to connect fields. Drag header to move. Click × to hide.',
                    'Increase SQL editor font (Ctrl++ or Ctrl+=)',
                    'Close table in diagram (no database changes)'):
            self.assertNotEqual(ui(key,'fa'),key)
        self.assertIn('ماهان پاکروان‌نسب',tr('qa_byline','fa'))
        self.assertIn('علی صیادی',tr('byline','fa'))
        self.assertIn(APP_VERSION,tr('v_notice','fa'))

    def test_main_diagram_uses_language_aware_menu(self):
        source=(ROOT/'src/widgets.py').read_text(encoding='utf8')
        self.assertIn('self.diagram', (ROOT/'src/app.py').read_text(encoding='utf8'))
        self.assertIn('menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft',source)
        self.assertIn("self.diagram.set_language(self.lang)",(ROOT/'src/app.py').read_text(encoding='utf8'))
        self.assertNotIn('card.setMaximumHeight(520)',source)
        self.assertIn('surface.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)',source)

try:
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QScrollArea
    from PySide6.QtCore import Qt
    from widgets import Diagram, WelcomePanel
    from core import LabDatabase, Column
    QT=True
except ImportError:
    QT=False

@unittest.skipUnless(QT,'PySide6 is not installed in this environment')
class QtPersianLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_compact_welcome_both_languages_small_and_large_viewports(self):
        for lang in ('fa','en'):
            panel=WelcomePanel(lang,lambda:None,lambda:None,lambda:None)
            for width,height in ((360,420),(580,540),(950,750)):
                panel.resize(width,height)
                panel.show();self.app.processEvents()
                card=panel.findChild(QFrame,'welcomeCard')
                self.assertIsNotNone(card)
                self.assertLessEqual(card.width(),470)
                self.assertGreaterEqual(card.height(),card.layout().minimumSize().height())
                self.assertTrue(panel.findChild(QScrollArea,'welcomeScroll'))
                authors=panel.findChildren(QLabel,'welcomeAuthor')
                self.assertEqual(len(authors),2)
                for author in authors:
                    self.assertGreater(author.height(),0)
            panel.close()

    def test_diagram_table_popup_translations_switch_at_runtime(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            db=LabDatabase(Path(folder)/'localization.db')
            db.create_table('Department',[Column('ID','INT',True,True,True)])
            diagram=Diagram('dark')
            diagram.set_db(db)
            diagram.set_language('fa')
            self.assertEqual(diagram.language,'fa')
            self.assertIn('ستون',diagram.toolTip())
            self.assertIn('بستن',diagram.nodes['Department']._close_tip.toolTip())
            diagram.set_language('en')
            self.assertIn('Drag',diagram.toolTip())
            diagram.close();db.close()
