"""Portable distribution source smoke tests (no Qt required)."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PortabilitySourceTests(unittest.TestCase):
    def test_cross_platform_files_are_shipped(self):
        for name in ('run_unix.sh','build_linux.sh','build_macos.sh',
                     'build_windows.bat','assets/app.png',
                     '.github/workflows/cross-platform-build.yml'):
            self.assertTrue((ROOT/name).is_file(),name)

    def test_unix_builds_do_not_require_windows_paths(self):
        for name in ('run_unix.sh','build_linux.sh','build_macos.sh'):
            body=(ROOT/name).read_text(encoding='utf-8')
            self.assertNotIn(r'C:\\',body)
            self.assertIn('set -euo pipefail',body)

    def test_same_codebase_all_platforms(self):
        app=(ROOT/'src/app.py').read_text(encoding='utf-8')
        self.assertIn('from version_info import APP_VERSION', app)
        self.assertIn('platform.machine()',app)
        self.assertIn('app.png',app)

if __name__=='__main__':unittest.main()
