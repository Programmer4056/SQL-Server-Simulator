# SQL Server Simulator v0.8.0 | Cross-platform beta

- Shared Python/PySide6/SQLite source for Windows/macOS/Linux.
- Native font and window icon selection, cross-platform project folder fallback, OS-aware bug report.
- Linux and macOS run/build scripts, a Linux desktop entry, and bundled PNG icon.
- GitHub Actions build matrix for Windows x64, Ubuntu x64, macOS Intel and macOS Apple Silicon.
- Existing teaching database behavior and constraints retained from v0.7.0.

**Limitations:** Only backend tests can be verified in this development environment. Compiled builds and GUI behaviors on each target OS require target-runner testing. Linux builds .tar.gz and .deb (not AppImage yet). macOS app is delivered as .zip/.dmg, unsigned and unnotarized.
