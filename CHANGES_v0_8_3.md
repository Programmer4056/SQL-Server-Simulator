# SQL Server Simulator v0.8.3 | تکمیل دستورات T-SQL آموزشی و زوم نمودار

## قابلیت‌های جدید
- **CREATE VIEW dbo.Name AS SELECT ...**: ساخت یک نمای واقعی SQLite، با امکان پرس‌وجو، ذخیره و نمایش در Object Explorer. ساخت نمای نامعتبر به‌شکل تراکنشی بازگردانده می‌شود.
- **CREATE PROC / CREATE PROCEDURE**: تعریف Stored Procedure آموزشی با پارامترهای ورودی، نگهداری در دیتابیس، و اجرای `EXEC` یا `EXECUTE`. دستورات پشتیبانی‌شده داخل بدنه: `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `SET NOCOUNT ON`. دستورهای ویرایش داده در یک تراکنش اجرا می‌شوند.
- **CREATE FUNCTION**: تعریف تابع اسکالر دارای `RETURNS ... AS BEGIN RETURN expression END` با پارامتر ورودی؛ قابل فراخوانی از `SELECT dbo.Name(...)`. پس از باز شدن مجدد دیتابیس ثبت می‌شود.
- **CREATE OR ALTER** برای سه نوع تعریف و **DROP VIEW/PROC/PROCEDURE/FUNCTION** برای حذف.
- اضافه شدن پوشه‌های Views، Stored Procedures و Scalar Functions به Object Explorer.
- برجسته‌سازی واژه‌های `PROC`، `PROCEDURE`، `VIEW`، `FUNCTION`، `EXEC`، `RETURNS` و `GO` در SQL Editor.
- نگه‌داشتن اصلاح قبلی **Zoom In / Zoom Out** و رفع گیرکردن زوم بعد از Auto Layout در نمودارهای بزرگ.

## محدودیت‌های روشن
- موتور اصلی هنوز SQLite است، نه SQL Server. این دستورات **زیرمجموعه آموزشی** T-SQL هستند.
- Procedureها از IF/WHILE، Cursor، TRY/CATCH، OUTPUT، SQL پویا و چند Result Set مجزا پشتیبانی نمی‌کنند.
- Functionها در این نسخه فقط **اسکالر تک‌عبارتی** هستند. Table-Valued Function و بدنه چنددستوری پشتیبانی نمی‌شوند.
- دستورات CREATE VIEW/PROC/FUNCTION را در یک Batch مستقل قرار دهید؛ برای اجرای دستور بعدی از `GO` در خط مجزا استفاده کنید.
- دستورهای ناسازگار به‌صراحت خطا می‌دهند. این قابلیت‌ها نباید برای اجرای کد ناشناخته/غیرقابل‌اعتماد یا سناریوهای تولیدی به‌کار روند.

نمونه آماده: `examples/TSQL_Modules_v0_8_3.sql`.
