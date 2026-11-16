"""Packaging smoke checks even in runtimes without graphical Qt."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class StaticUiFeatureChecks(unittest.TestCase):
    def test_all_requested_features_are_wired(self):
        app=(ROOT/'src/app.py').read_text(encoding='utf-8')
        editor=(ROOT/'src/widgets.py').read_text(encoding='utf-8')
        for name in ('queryZoomInButton','queryZoomOutButton','queryZoomResetButton',
                     'Open SQL Script','Edit Selected Record','Delete Selected Record',
                     'Ctrl++','Ctrl+=','Ctrl+-','Ctrl+0'):
            self.assertIn(name,app,name)
        for method in ('def zoom_in_text','def zoom_out_text','def zoom_reset_text',
                       'def wheelEvent','def request_completion','def insert_completion',
                       'class SQLEditor'):
            self.assertIn(method,editor,method)
        self.assertIn('def delete_record', (ROOT/'src/model_ext.py').read_text(encoding='utf-8'))
        self.assertIn('def read_sql_script',(ROOT/'src/sql_script_loader.py').read_text(encoding='utf-8'))
if __name__=='__main__':unittest.main()
