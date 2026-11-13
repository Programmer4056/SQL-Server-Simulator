<h1 dir="rtl" align="right">شبیه‌ساز آموزشی SQL Server</h1>

<p dir="rtl" align="right">
<strong>SQL Server Simulator | نسخه ۰.۶.۱ (آزمایشی)</strong><br>
<strong>طراحی و توسعه:</strong> علی صیادی<br>
<strong>سیستم‌عامل:</strong> ویندوز ۱۰ و ۱۱<br>
<strong>رابط کاربری:</strong> انگلیسی و فارسی، با تم روشن و تاریک
</p>

<p dir="rtl" align="right">
<a href="README_FA.md">📘 راهنمای کامل فارسی</a> |
<a href="README_EN.md">English documentation</a> |
<a href="CHANGES_v0_6_1.md">تغییرات نسخه ۰.۶.۱</a>
</p>

<hr>

<h2 dir="rtl" align="right">🎓 معرفی پروژه</h2>

<p dir="rtl" align="right">
<strong>SQL Server Simulator</strong> یک نرم‌افزار دسکتاپ آموزشی برای یادگیری طراحی و مدیریت پایگاه داده‌های رابطه‌ای است. محیط برنامه با الهام از <strong>SQL Server Management Studio (SSMS)</strong> طراحی شده است تا دانشجویان بتوانند بدون نصب موتور SQL Server، به‌صورت گرافیکی پایگاه داده بسازند، جدول‌ها را ویرایش کنند، رابطه‌ها را در <code>Database Diagram</code> ترسیم کنند و قواعد کلید اصلی و خارجی را در عمل بیاموزند.
</p>

<p dir="rtl" align="right">
<strong>مهم:</strong> این برنامه محصول مایکروسافت یا جایگزین کامل SQL Server نیست. موتور واقعی آن <strong>SQLite</strong> است و بخشی از امکانات SQL Server را برای اهداف آموزشی شبیه‌سازی می‌کند. بنابراین اجرای تمام دستورات <code>T-SQL</code> و سازگاری کامل با SSMS تضمین نمی‌شود.
</p>

<h2 dir="rtl" align="right">✨ قابلیت‌های اصلی</h2>

<ul dir="rtl">
<li><strong>ساخت بدون کدنویسی:</strong> ایجاد پایگاه داده و جدول با <code>Wizard</code> و <code>Table Designer</code>.</li>
<li><strong>طراحی ستون‌ها:</strong> تعریف نام، نوع داده، طول، مقدارپذیری تهی (<code>NULL</code>)، کلید اصلی و کلید خارجی.</li>
<li><strong>نوع داده‌های آشنا:</strong> گزینه‌هایی مانند <code>INT</code>، <code>NVARCHAR(50)</code>، <code>NVARCHAR(MAX)</code> و <code>DECIMAL(18,2)</code>.</li>
<li><strong>شناسه خودکار:</strong> تنظیم <code>IDENTITY</code> با مقادیر <code>Seed</code> و <code>Increment</code> در امکانات پشتیبانی‌شده.</li>
<li><strong>نمودار تعاملی:</strong> ساخت و ویرایش جدول‌ها، جابه‌جایی کارت‌ها و اتصال مستقیم فیلدها در <code>Database Diagram</code>.</li>
<li><strong>مدیریت رابطه‌ها:</strong> انتخاب خط ارتباط، مشاهده مشخصات و حذف رابطه با تأیید کاربر.</li>
<li><strong>ورود و مشاهده داده‌ها:</strong> فرم ورود رکورد، نمایش جدولی اطلاعات و ویرایشگر دستورهای SQL.</li>
<li><strong>خروجی اسکریپت:</strong> تولید فایل <code>.sql</code> برای ساختار جدول‌ها، داده‌ها یا هر دو.</li>
<li><strong>امکانات ظاهری:</strong> انتخاب زبان انگلیسی یا فارسی و تم روشن یا تاریک.</li>
</ul>

<h2 dir="rtl" align="right">🔗 انواع روابط و قواعد پایگاه داده</h2>

<table dir="rtl">
<thead>
<tr><th>نوع رابطه</th><th>نحوه پیاده‌سازی آموزشی</th></tr>
</thead>
<tbody>
<tr><td>یک‌به‌یک (۱:۱)</td><td>کلید اصلی مشترک: کلید جدول فرزند، هم‌زمان <code>PK</code> و <code>FK</code> است.</td></tr>
<tr><td>یک‌به‌چند (۱:N)</td><td>کلید سمت «یک» در جدول سمت «چند» به‌عنوان <code>FK</code> ثبت می‌شود.</td></tr>
<tr><td>چندبه‌چند (N:M)</td><td>جدول واسط با دو کلید خارجی ساخته می‌شود؛ کلید اصلی ترکیبی یا شناسه مستقل قابل استفاده است.</td></tr>
<tr><td>بازگشتی (Self-reference)</td><td>یک فیلد خارجی به کلید اصلی همان جدول ارجاع می‌دهد؛ مانند <code>ManagerID</code>.</td></tr>
</tbody>
</table>

<p dir="rtl" align="right">
<strong>جامعیت ارجاعی:</strong> مقدار غیرتهیِ کلید خارجی باید به یک کلید معتبر در جدول مرجع اشاره کند. اگر فیلد خارجی اختیاری باشد، مقدار <code>NULL</code> می‌تواند مجاز باشد. هنگام ایجاد یا تغییر رابطه، برنامه ناسازگاری انواع داده و وجود مقادیر ارجاعی نامعتبر را بررسی می‌کند.
</p>

<h2 dir="rtl" align="right">🖱️ طراحی رابطه بدون نوشتن کوئری</h2>

<ol dir="rtl">
<li>پایگاه داده را باز کنید و وارد <code>Database Diagram</code> شوید.</li>
<li>جدول‌ها را ایجاد کنید یا از طریق گزینه <code>Design Table</code> آن‌ها را تغییر دهید.</li>
<li>برای اتصال، یک فیلد کلید اصلی را به فیلد مقصد بکشید؛ یا گزینه <code>Draw Link (2 clicks)</code> را فعال کنید و دو فیلد را انتخاب کنید.</li>
<li>در پنجره <code>Relationship Wizard</code> نوع ارتباط و فیلدهای انتخاب‌شده را بررسی کنید.</li>
<li>برای حذف ارتباط، روی خط آن کلیک کنید و گزینه <code>Delete Relationship</code> را انتخاب کنید. حذف رابطه با تأیید انجام می‌شود؛ خود جدول و داده‌هایش باقی می‌مانند.</li>
</ol>

<h2 dir="rtl" align="right">🛠️ فناوری‌های استفاده‌شده</h2>

<table dir="rtl">
<thead><tr><th>بخش</th><th>فناوری</th></tr></thead>
<tbody>
<tr><td>زبان برنامه‌نویسی</td><td><code>Python 3.12</code></td></tr>
<tr><td>رابط دسکتاپ</td><td><code>PySide6 / Qt 6</code></td></tr>
<tr><td>موتور پایگاه داده</td><td><code>SQLite 3</code></td></tr>
<tr><td>طراحی نمودار</td><td><code>QGraphicsView / QGraphicsScene</code></td></tr>
<tr><td>ساخت فایل اجرایی ویندوز</td><td><code>PyInstaller</code></td></tr>
<tr><td>نصب‌کننده</td><td><code>Inno Setup 6</code></td></tr>
<tr><td>آزمون‌های خودکار</td><td><code>unittest</code></td></tr>
</tbody>
</table>

<h2 dir="rtl" align="right">💻 راه‌اندازی روی ویندوز</h2>

<ol dir="rtl">
<li>نسخه <strong>Python 3.10 یا جدیدتر</strong> را نصب کنید.</li>
<li>مخزن را دانلود یا کلون کنید و وارد پوشه اصلی پروژه شوید.</li>
<li>فایل <code>run_windows.bat</code> را اجرا کنید. در اولین اجرا، نصب بسته‌های لازم به اینترنت نیاز دارد.</li>
<li>برای ساخت نسخه مستقل ویندوز، فایل <code>build_windows.bat</code> را اجرا کنید.</li>
</ol>

<p dir="rtl" align="right">یا برنامه را با دستورهای زیر از داخل پوشه پروژه اجرا کنید:</p>

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\main.py
```

<p dir="rtl" align="right">
<strong>محل خروجی EXE بعد از ساخت موفق:</strong><br>
<code>dist\SQLServerSimulator\SQLServerSimulator.exe</code><br>
برای اجرا یا انتقال برنامه، کل پوشه <code>SQLServerSimulator</code> را نگه دارید. ساخت فایل نصب <code>Setup</code> به نصب <code>Inno Setup 6</code> نیاز دارد. خروجی‌های کامپایل‌شده به‌طور پیش‌فرض داخل سورس این مخزن قرار ندارند.
</p>

<h2 dir="rtl" align="right">🧪 اجرای آزمون‌ها</h2>

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

<p dir="rtl" align="right">
آزمون‌های رابط گرافیکی به کتابخانه <code>PySide6</code> و یک محیط قابل اجرای Qt نیاز دارند. وضعیت ساخت خودکار ویندوز را می‌توان در تب <code>Actions</code> مخزن مشاهده کرد.
</p>

<h2 dir="rtl" align="right">📁 نمونه‌های آموزشی</h2>

<ul dir="rtl">
<li><a href="examples/Diagram_Training_v0_4.db"><code>Diagram_Training_v0_4.db</code></a>: نمونه ارتباط‌های یک‌به‌یک، یک‌به‌چند، چندبه‌چند و بازگشتی.</li>
<li><a href="examples/Drag_to_Connect_v0_5.db"><code>Drag_to_Connect_v0_5.db</code></a>: نمونه تمرین اتصال فیلدبه‌فیلد.</li>
<li><a href="examples/Sample_SQLServer_2022.sql"><code>Sample_SQLServer_2022.sql</code></a>: نمونه خروجی اسکریپتی برای SQL Server.</li>
</ul>

<p dir="rtl" align="right">
<strong>درباره پشتیبان‌گیری:</strong> خروجی <code>.sql</code>، اسکریپت ساختار و داده است و با بکاپ باینری واقعی SQL Server با پسوند <code>.bak</code> تفاوت دارد. سازگاری تمام خروجی‌ها با همه نسخه‌های SQL Server آزمایش نشده است.
</p>

<h2 dir="rtl" align="right">🐞 گزارش خطا و پیشنهادها</h2>

<p dir="rtl" align="right">
این نسخه <strong>آزمایشی</strong> است و ممکن است باگ داشته باشد. در صورت مشاهده مشکل، نام بخش مربوط، مراحل ایجاد خطا و در صورت امکان تصویر یا متن پیام خطا را ارسال کنید:
</p>

<p dir="rtl" align="right">
📧 <a href="mailto:Ali.sayyadi200@gmail.com?subject=SQL%20Server%20Simulator%20v0.6.1%20-%20Bug%20Report">Ali.sayyadi200@gmail.com</a>
</p>

<h2 dir="rtl" align="right">📄 حقوق و مجوزها</h2>

<p dir="rtl" align="right">
<strong>طراحی و توسعه:</strong> علی صیادی. برای کد اختصاصی پروژه هنوز مجوز متن‌باز مشخصی اعلام نشده است. مجوزهای کتابخانه‌ها و اجزای شخص ثالث در فایل <a href="LICENSE_NOTICES.txt"><code>LICENSE_NOTICES.txt</code></a> توضیح داده شده‌اند. نام‌های Microsoft و SQL Server متعلق به صاحبان نشان‌های تجاری آن‌ها هستند و این پروژه وابستگی رسمی به مایکروسافت ندارد.
</p>
