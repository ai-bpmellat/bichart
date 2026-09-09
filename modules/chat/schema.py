"""BI schema text injected into LLM SQL-generation prompts."""

SCHEMA_DESCRIPTION = """
Tables:

dim_date(date_key INTEGER PK, full_date DATE, day_name TEXT, month_name TEXT,
          year INTEGER, month INTEGER, day INTEGER, is_weekend BOOLEAN, is_holiday BOOLEAN)

dim_customer(customer_id INTEGER PK, customer_name TEXT, access_key TEXT, role TEXT)
  -- the PSP's contracted client company that owns merchants

dim_category(category_id INTEGER PK, category_name TEXT)
  -- standardized Persian merchant verticals; valid category_name values ONLY:
  1 فروشگاه‌های مواد غذایی و سوپرمارکت‌ها
  2 رستوران‌ها، فست‌فودها و کافه‌ها
  3 پوشاک و کیف و کفش
  4 داروخانه‌ها و مراکز درمانی
  5 خدمات پزشکی و آزمایشگاهی
  6 جایگاه‌های سوخت
  7 هتل‌ها و مراکز اقامتی
  8 حمل‌ونقل و تاکسی
  9 آموزشگاه‌ها و مراکز آموزشی
  10 خدمات فنی و تعمیراتی
  11 فروش لوازم خانگی و الکترونیک
  12 طلافروشی و جواهرات
  13 خدمات دولتی و عمومی
  14 خیریه‌ها و سازمان‌های غیرانتفاعی
  15 کسب‌وکارهای اینترنتی و تجارت الکترونیک

dim_merchant(merchant_id INTEGER PK, merchant_name TEXT, merchant_code TEXT,
             mcc TEXT, category_id INTEGER FK -> dim_category, category TEXT,
             city TEXT, owner_customer_id INTEGER FK -> dim_customer, is_active BOOLEAN)
  -- category is denormalized copy of dim_category.category_name (Persian)

dim_terminal(terminal_id INTEGER PK, terminal_serial TEXT, merchant_id INTEGER FK -> dim_merchant,
             terminal_type TEXT, install_date DATE, status TEXT)
  -- status values: 'active' or 'inactive' (lowercase)

fact_transactions(transaction_id INTEGER PK, date_key INTEGER FK -> dim_date,
                   terminal_id INTEGER FK -> dim_terminal, merchant_id INTEGER FK -> dim_merchant,
                   transaction_time DATETIME, amount REAL, currency TEXT, status TEXT
                   (approved/declined/reversed), card_pan_masked TEXT, response_code TEXT,
                   settlement_date DATE, channel TEXT (POS/ONLINE/MOBILE))
  -- date_key is INTEGER YYYYMMDD (e.g. 20260319), NOT a SQL date.
  -- NEVER use date(), strftime(), or compare date_key to date('now', ...).
  -- ALWAYS join dim_date and use dim_date.full_date for any date filter or month/year logic.

Notes:
- CRITICAL date rules:
  * Join: JOIN dim_date d ON f.date_key = d.date_key
  * Filter: WHERE d.full_date >= date('now','-6 months')  — NOT f.date_key >= date(...)
  * Month/year: strftime('%Y-%m', d.full_date)  — NOT strftime(..., f.date_key)
  * "yesterday" / "دیروز": WHERE d.full_date = date('now','-1 day')
  * "last month" / "ماه گذشته": WHERE d.full_date >= date('now','start of month','-1 month')
    AND d.full_date < date('now','start of month')
  * Use SQLite modifier 'start of month' — NEVER 'first day of month' (returns NULL in SQLite).
  * Mock data spans approximately the last 6 months through yesterday (rolling window from db_mock.py).
- Status rules:
  * dim_terminal.status: 'active' / 'inactive' (lowercase) — do not use 'Active'
  * fact_transactions.status: approved / declined / reversed
- merchant_name, customer_name, category, and category_name are in Persian (Farsi).
- For category breakdowns, join dim_merchant to dim_category on category_id,
  or use dim_merchant.category directly (same Persian labels).
- Always join through merchant_id when filtering by merchant.
- Do not add LIMIT unless the user asks for a specific number of rows (e.g. top 10).
"""
