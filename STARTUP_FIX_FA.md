# SQL Server Simulator 0.2 - Startup Fix

این بسته خطای زیر را اصلاح می‌کند:

`AttributeError: type object 'PySide6.QtWidgets.QPlainTextEdit' has no attribute 'ExtraSelection'`

## روش سریع (بدون نصب مجدد پیش‌نیازها)

1. فایل‌های ZIP کوچک اصلاحیه را در پوشه فعلی پروژه استخراج کن؛ جایی که `build_windows.bat` و پوشه `src` قرار دارند.
2. فایل‌ها را با فایل‌های قبلی جایگزین کن؛ **پوشه `.venv` را حذف نکن**.
3. در CMD از ریشه پروژه اجرا کن:

   `.venv\Scripts\python.exe src\main.py`

4. اگر برنامه باز شد، آن را ببند و `build_windows.bat` را برای ساخت EXE جدید اجرا کن.
5. فایل اجرایی جدید در `dist\SQLServerSimulator\SQLServerSimulator.exe` قرار می‌گیرد.

در نسخه اصلاح‌شده، قبل از بسته‌بندی، آزمون آغاز به کار رابط Qt با `QT_QPA_PLATFORM=offscreen` اجرا می‌شود تا این نوع خطا زودتر مشخص شود. این تست جای بررسی نهایی ظاهر و عملکرد روی ویندوز را نمی‌گیرد.

**تغییر کد:** `QTextEdit.ExtraSelection()` به جای `QPlainTextEdit.ExtraSelection()`، و اضافه‌شدن import کلاس `QTextEdit`.
