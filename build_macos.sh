#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt 'pyinstaller>=6.8,<8'
.venv/bin/python -c "from PySide6.QtWidgets import QApplication"
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
# Generate a macOS-compatible .icns with Apple's own iconutil.
rm -rf build/app.iconset
mkdir -p build/app.iconset
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" assets/app.png --out "build/app.iconset/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" assets/app.png --out "build/app.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns build/app.iconset -o build/app.icns
.venv/bin/python -m PyInstaller --noconfirm --clean --windowed --onedir \
  --name SQLServerSimulator --exclude-module tkinter \
  --icon "$PWD/build/app.icns" --add-data "$PWD/assets:assets" \
  --distpath dist --workpath build --specpath build src/main.py
mkdir -p release
if [ ! -d dist/SQLServerSimulator.app ]; then
  echo 'macOS application bundle missing after packaging.' >&2
  exit 1
fi
# Preserve app bundle symlinks/metadata. Signing/notarization is NOT included.
ditto -c -k --sequesterRsrc --keepParent dist/SQLServerSimulator.app \
  "release/SQL_Server_Simulator_v0.8.9_macOS_$(uname -m).zip"
# Optional native drag-to-Applications disk image.
rm -rf build/dmg-root
mkdir -p build/dmg-root
cp -R dist/SQLServerSimulator.app build/dmg-root/
ln -s /Applications build/dmg-root/Applications
hdiutil create -volname 'SQL Server Simulator' -srcfolder build/dmg-root \
  -ov -format UDZO "release/SQL_Server_Simulator_v0.8.9_macOS_$(uname -m).dmg" >/dev/null
echo 'macOS outputs: release/*.zip and release/*.dmg'

