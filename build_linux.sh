#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt 'pyinstaller>=6.8,<8'
.venv/bin/python -c "from PySide6.QtWidgets import QApplication"
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m PyInstaller --noconfirm --clean --windowed --onedir \
  --name SQLServerSimulator --exclude-module tkinter \
  --add-data "$PWD/assets:assets" --distpath dist --workpath build \
  --specpath build src/main.py
mkdir -p release
cp -f README.md README_EN.md README_FA.md LICENSE_NOTICES.txt dist/SQLServerSimulator/
install -m 0644 assets/app.png dist/SQLServerSimulator/app.png
cp linux/SQLServerSimulator.desktop dist/SQLServerSimulator/
install -m 0755 linux/run.sh dist/SQLServerSimulator/run.sh
tar -czf release/SQL_Server_Simulator_v0.8.9_Linux_$(uname -m).tar.gz -C dist SQLServerSimulator
# Debian/Ubuntu native package when dpkg-deb is available.
if command -v dpkg-deb >/dev/null 2>&1; then
  DEBROOT=build/deb-root
  rm -rf "$DEBROOT"
  mkdir -p "$DEBROOT/DEBIAN" "$DEBROOT/opt/sql-server-simulator" \
    "$DEBROOT/usr/bin" "$DEBROOT/usr/share/applications" \
    "$DEBROOT/usr/share/icons/hicolor/256x256/apps"
  cp -a dist/SQLServerSimulator/. "$DEBROOT/opt/sql-server-simulator/"
  cp linux/SQLServerSimulator.desktop "$DEBROOT/usr/share/applications/sql-server-simulator.desktop"
  sed -i 's/^Exec=.*/Exec=sql-server-simulator/' "$DEBROOT/usr/share/applications/sql-server-simulator.desktop"
  sed -i 's/^Icon=.*/Icon=sql-server-simulator/' "$DEBROOT/usr/share/applications/sql-server-simulator.desktop"
  cp assets/app.png "$DEBROOT/usr/share/icons/hicolor/256x256/apps/sql-server-simulator.png"
  cat > "$DEBROOT/usr/bin/sql-server-simulator" <<'SH'
#!/bin/sh
exec /opt/sql-server-simulator/SQLServerSimulator "$@"
SH
  chmod 0755 "$DEBROOT/usr/bin/sql-server-simulator"
  cat > "$DEBROOT/DEBIAN/control" <<EOF
Package: sql-server-simulator
Version: 0.8.9
Section: education
Priority: optional
Architecture: $(dpkg --print-architecture)
Maintainer: Ali Sayyadi <Ali.sayyadi200@gmail.com>
Description: Educational SQL Server-inspired database simulator
 Native PySide6 desktop application for practicing PK, FK, ERD and SQLite.
EOF
  dpkg-deb --build "$DEBROOT" "release/SQL_Server_Simulator_v0.8.9_Linux_$(dpkg --print-architecture).deb"
fi
echo 'Linux outputs: release/*.tar.gz and, on Debian/Ubuntu, release/*.deb'

