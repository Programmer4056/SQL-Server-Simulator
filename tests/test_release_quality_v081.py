"""Release integrity checks that run without Qt or access to external services."""
import re
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from version_info import APP_VERSION, REPORT_EMAIL
from i18n import tr
from core import LabDatabase, Column, LabError
from model_ext import insert_data
from tsql_compat import run_script

class ReleaseConsistencyTests(unittest.TestCase):
    def test_single_canonical_version(self):
        self.assertEqual(APP_VERSION,'0.8.9')
        app = (ROOT/'src/app.py').read_text(encoding='utf-8')
        self.assertIn('from version_info import APP_VERSION',app)
        self.assertNotIn("APP_VERSION='0.7.0'",app)
        for filename in ('installer.iss','build_windows.bat',
                         'build_linux.sh','build_macos.sh',
                         '.github/workflows/cross-platform-build.yml'):
            self.assertIn(APP_VERSION,(ROOT/filename).read_text(encoding='utf-8'),filename)

    def test_about_messages_show_current_version_in_both_languages(self):
        for lang in ('fa','en'):
            about=tr('about_text',lang)
            notice=tr('v_notice',lang)
            self.assertIn(APP_VERSION,about)
            self.assertIn(APP_VERSION,notice)
            self.assertNotIn('0.6.0',about)
            self.assertNotIn('0.7.0',about)
            self.assertIn(REPORT_EMAIL,about)
        self.assertIn('dir="rtl"',tr('about_text','fa'))
        self.assertIn('dir="ltr"',tr('about_text','en'))
        self.assertIn(f'<span dir="ltr">v{APP_VERSION}</span>',tr('about_text','fa'))

    def test_persian_notice_is_bidi_safe(self):
        notice=tr('v_notice','fa')
        self.assertIn('\u200e'+APP_VERSION+'\u200e',notice)
        self.assertIn('نسخه آزمایشی',notice)

    def test_no_hardcoded_version_in_translations(self):
        translation=(ROOT/'src/i18n.py').read_text(encoding='utf-8')
        self.assertNotRegex(translation,r"(?:v_notice|about_text).*?(?:0[.]6[.]0|0[.]7[.]0)")

    def test_release_archives_configured_consistently(self):
        setup=(ROOT/'installer.iss').read_text(encoding='utf-8')
        self.assertIn(f'AppVersion "{APP_VERSION}"',setup)
        self.assertIn('Setup_v'+APP_VERSION,setup)
        workflow=(ROOT/'.github/workflows/cross-platform-build.yml').read_text(encoding='utf-8')
        for platform in ('Windows','Linux','macOS'):
            self.assertIn(platform,workflow)
        self.assertNotIn('v0.8.0-',workflow)

    def test_diagram_toolbar_is_scrollable_and_laid_out_after_all_buttons(self):
        app=(ROOT/'src/app.py').read_text(encoding='utf-8')
        self.assertIn('def resize_diagram_toolbar',app)
        self.assertIn('self.diagram_action_host.setMinimumWidth(needed.width())',app)
        self.assertIn('ScrollBarAsNeeded',app)
        self.assertGreater(app.index('self.diagram_actions_scroll.setWidget(action_host)'),
                           app.index("zoom_button.setObjectName('diagramZoomButton')"))

class UserDataSafetyTests(unittest.TestCase):
    def test_reject_orphan_after_relationship_creation(self):
        with tempfile.TemporaryDirectory() as dirname:
            db=LabDatabase(Path(dirname)/'constraints.db')
            try:
                db.create_table('Dept',[Column('ID','INT',True,True,True)])
                db.create_table('Member',[Column('ID','INT',True,True,True),Column('DeptID','INT')])
                db.one_to_many('Dept','Member','DeptID',required=False)
                with self.assertRaises(LabError):
                    insert_data(db,'Member',{'DeptID':900})
                self.assertEqual(db.connection.execute('SELECT count(*) FROM Member').fetchone()[0],0)
                insert_data(db,'Dept',{})
                insert_data(db,'Member',{'DeptID':1})
                self.assertEqual(db.check_integrity(),[])
            finally:
                db.close()

    def test_sql_switching_unknown_database_is_not_silent(self):
        with tempfile.TemporaryDirectory() as dirname:
            with self.assertRaisesRegex(LabError,'not found'):
                run_script(None,'USE MissingDb;',dirname)
            self.assertEqual(list(Path(dirname).glob('*.db')),[])

    def test_rebuild_on_failed_drop_preserves_references(self):
        with tempfile.TemporaryDirectory() as dirname:
            db=LabDatabase(Path(dirname)/'constraints.db')
            try:
                db.create_table('Book',[Column('ID','INT',True,True,True)])
                db.create_table('Loan',[Column('ID','INT',True,True,True),Column('BookID','INT')])
                db.one_to_many('Book','Loan','BookID',False)
                insert_data(db,'Book',{})
                insert_data(db,'Loan',{'BookID':1})
                with self.assertRaises(LabError): db.drop_table('Book')
                self.assertIn('Book',db.tables())
                self.assertEqual(len(db.foreign_keys('Loan')),1)
                self.assertEqual(db.check_integrity(),[])
            finally:
                db.close()

if __name__=='__main__': unittest.main()
