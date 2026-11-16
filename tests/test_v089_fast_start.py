"""Ensure the fast-start distribution remains offline and one-folder based."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FastStartPackagingTests(unittest.TestCase):
    def test_fast_builder_is_onedir_not_onefile(self):
        body = (ROOT / 'build_windows_fast_start.bat').read_text(encoding='utf-8')
        self.assertIn('--onedir', body)
        self.assertNotIn('--onefile', body)
        self.assertIn('dist\\SQLServerSimulator\\SQLServerSimulator.exe', body)
        self.assertIn('installer.iss', body)

    def test_fast_builder_does_not_fetch_deps(self):
        body = (ROOT / 'build_windows_fast_start.bat').read_text(encoding='utf-8').lower()
        self.assertNotIn('-m pip install', body)
        self.assertNotIn('curl ', body)
        self.assertNotIn('wget ', body)

    def test_setup_bundles_directory_and_launches_after_install(self):
        installer = (ROOT / 'installer.iss').read_text(encoding='utf-8')
        self.assertIn('Source: "dist\\SQLServerSimulator\\*"', installer)
        self.assertIn('recursesubdirs', installer)
        self.assertIn('[Run]', installer)
        self.assertIn('postinstall', installer)


if __name__ == '__main__':
    unittest.main()
