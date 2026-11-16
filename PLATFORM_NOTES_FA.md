# راهنمای اجرای چندسکویی (نسخه 0.8.7)

این نسخه از یک کد مشترک Python، PySide6 و SQLite استفاده می‌کند. فایل اجرایی هر سیستم‌عامل جداگانه و روی همان سیستم‌عامل ساخته می‌شود.

## Windows

فایل `run_windows.bat` برای اجرای سورس و `build_windows.bat` برای تولید EXE و در صورت نصب بودن Inno Setup 6، فایل Setup به کار می‌رود.

## macOS

Python 3.12 و ابزارهای خط فرمان Xcode را نصب کنید. سپس از ترمینال در پوشه پروژه:

```bash
bash run_unix.sh
```

برای ساخت فایل `.app`، بسته ZIP و نصب‌کننده DMG:

```bash
bash build_macos.sh
```

مسیر خروجی: `release/SQL_Server_Simulator_v0.8.3_macOS_<architecture>.zip`. معماری‌های `x86_64` و `arm64` باید هرکدام روی ماشین مناسب ساخته شوند. برنامه هنوز امضای Developer ID و Notarization ندارد؛ برای انتشار عمومی قابل‌اعتماد، لازم است این مراحل انجام شوند.

## Linux

Python 3.12 و پکیج `python3-venv` را نصب کنید. بسته به توزیع، پیش‌نیازهای Qt/XCB نیز لازم‌اند. سپس:

```bash
bash run_unix.sh
# یا برای بسته‌بندی
bash build_linux.sh
```

مسیر خروجی: `release/SQL_Server_Simulator_v0.8.3_Linux_<architecture>.tar.gz`. پس از استخراج، داخل پوشه `SQLServerSimulator` فایل `./run.sh` را اجرا کنید. این همچنین روی توزیع‌های مبتنی بر Debian/Ubuntu بسته `.deb` ساخته می‌شود. بسته AppImage هنوز ارائه نشده است و ممکن است به کتابخانه‌های گرافیکی سیستم نیاز باشد.

## GitHub Actions

فایل `.github/workflows/cross-platform-build.yml` چهار Job شامل Windows x64، Linux x64، macOS Intel و macOS Apple Silicon دارد. کد را به شاخه `main` بفرستید، وارد قسمت Actions شوید و Workflow را اجرا کنید. خروجی هر Job در Artifacts همان اجرا قرار می‌گیرد.

**توجه:** تا زمانی که Job های GitHub Actions و اجرای GUI روی سیستم‌عامل‌های مقصد موفق نشوند، سازگاری عملی آن‌ها تأیید نشده است.
