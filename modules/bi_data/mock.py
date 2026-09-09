"""
db_mock.py
----------
Creates the SQLite schema (dim_date, dim_merchant, dim_terminal, fact_transactions)
and populates it with ~1,000 realistic rows for a PSP (Payment Service Provider)
operating in Iran. Merchant names are real-style Persian company names across
common verticals (retail chains, supermarkets, pharmacies, restaurants, fuel
stations, etc.) — useful as believable stand-ins for testing Text-to-SQL and
the authorization layer.

Run this once before starting the app:
    python db_mock.py

Re-running it wipes and rebuilds the database from scratch.
"""

import os
import random
import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship

from modules.bi_data.database import Base, engine, SessionLocal, SQLITE_PATH

random.seed(42)

# ---------------------------------------------------------------------------
# ORM MODELS
# ---------------------------------------------------------------------------

class DimDate(Base):
    __tablename__ = "dim_date"
    date_key = Column(Integer, primary_key=True)        # YYYYMMDD
    full_date = Column(Date, nullable=False, unique=True)
    day_name = Column(String(20))
    month_name = Column(String(20))
    year = Column(Integer)
    month = Column(Integer)
    day = Column(Integer)
    is_weekend = Column(Boolean, default=False)
    is_holiday = Column(Boolean, default=False)


class DimCategory(Base):
    """Standard merchant business verticals (Persian labels)."""
    __tablename__ = "dim_category"
    category_id = Column(Integer, primary_key=True)
    category_name = Column(String(80), nullable=False, unique=True)

    merchants = relationship("DimMerchant", back_populates="category_ref")


class DimMerchant(Base):
    __tablename__ = "dim_merchant"
    merchant_id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_name = Column(String(150), nullable=False)     # Persian company name
    merchant_code = Column(String(20), unique=True)
    mcc = Column(String(4))                                   # Merchant Category Code
    category_id = Column(Integer, ForeignKey("dim_category.category_id"), nullable=False)
    category = Column(String(80))                             # denormalized Persian label
    city = Column(String(50))
    owner_customer_id = Column(Integer, ForeignKey("dim_customer.customer_id"))
    is_active = Column(Boolean, default=True)

    terminals = relationship("DimTerminal", back_populates="merchant")
    owner = relationship("DimCustomer", back_populates="merchants")
    category_ref = relationship("DimCategory", back_populates="merchants")


class DimCustomer(Base):
    """
    Represents the PSP's contracted client/company. Used for the
    authorization layer: a logged-in customer can only query data
    belonging to merchants/terminals they own.
    """
    __tablename__ = "dim_customer"
    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_name = Column(String(150), nullable=False)
    access_key = Column(String(64), unique=True)   # simple API key for demo auth
    role = Column(String(20), default="customer")  # "customer" or "admin"

    merchants = relationship("DimMerchant", back_populates="owner")


class DimTerminal(Base):
    __tablename__ = "dim_terminal"
    terminal_id = Column(Integer, primary_key=True, autoincrement=True)
    terminal_serial = Column(String(30), unique=True)
    merchant_id = Column(Integer, ForeignKey("dim_merchant.merchant_id"))
    terminal_type = Column(String(20))      # POS, mPOS, Online
    install_date = Column(Date)
    status = Column(String(20), default="active")

    merchant = relationship("DimMerchant", back_populates="terminals")


class FactTransaction(Base):
    __tablename__ = "fact_transactions"
    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    date_key = Column(Integer, ForeignKey("dim_date.date_key"))
    terminal_id = Column(Integer, ForeignKey("dim_terminal.terminal_id"))
    merchant_id = Column(Integer, ForeignKey("dim_merchant.merchant_id"))
    transaction_time = Column(DateTime)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="IRR")
    status = Column(String(20))             # approved, declined, reversed
    card_pan_masked = Column(String(20))    # e.g. 603799******1234
    response_code = Column(String(10))
    settlement_date = Column(Date)
    channel = Column(String(20))            # POS, ONLINE, MOBILE


# ---------------------------------------------------------------------------
# MOCK DATA POOLS (Persian / Iranian PSP context)
# ---------------------------------------------------------------------------

MERCHANT_CATEGORIES = [
    "فروشگاه‌های مواد غذایی و سوپرمارکت‌ها",
    "رستوران‌ها، فست‌فودها و کافه‌ها",
    "پوشاک و کیف و کفش",
    "داروخانه‌ها و مراکز درمانی",
    "خدمات پزشکی و آزمایشگاهی",
    "جایگاه‌های سوخت",
    "هتل‌ها و مراکز اقامتی",
    "حمل‌ونقل و تاکسی",
    "آموزشگاه‌ها و مراکز آموزشی",
    "خدمات فنی و تعمیراتی",
    "فروش لوازم خانگی و الکترونیک",
    "طلافروشی و جواهرات",
    "خدمات دولتی و عمومی",
    "خیریه‌ها و سازمان‌های غیرانتفاعی",
    "کسب‌وکارهای اینترنتی و تجارت الکترونیک",
]

# Typical MCC per business vertical (for realistic mock data)
CATEGORY_MCC = [
    "5411",  # فروشگاه‌های مواد غذایی و سوپرمارکت‌ها
    "5812",  # رستوران‌ها، فست‌فودها و کافه‌ها
    "5651",  # پوشاک و کیف و کفش
    "5912",  # داروخانه‌ها و مراکز درمانی
    "8099",  # خدمات پزشکی و آزمایشگاهی
    "5541",  # جایگاه‌های سوخت
    "7011",  # هتل‌ها و مراکز اقامتی
    "4121",  # حمل‌ونقل و تاکسی
    "8299",  # آموزشگاه‌ها و مراکز آموزشی
    "7699",  # خدمات فنی و تعمیراتی
    "5732",  # فروش لوازم خانگی و الکترونیک
    "5944",  # طلافروشی و جواهرات
    "9399",  # خدمات دولتی و عمومی
    "8398",  # خیریه‌ها و سازمان‌های غیرانتفاعی
    "5999",  # کسب‌وکارهای اینترنتی و تجارت الکترونیک
]

MERCHANT_POOL = [
    ("فروشگاه زنجیره‌ای رفاه", 0),
    ("هایپراستار", 0),
    ("شهروند", 0),
    ("اتکا", 0),
    ("افق کوروش", 0),
    ("فروشگاه‌های زنجیره‌ای جانبو", 0),
    ("سوپرمارکت محله ما", 0),
    ("فروشگاه زنجیره‌ای فامیلی", 0),
    ("مجتمع تجاری پالادیوم", 0),
    ("نان‌سرای تک‌نان", 0),
    ("قنادی شیرین‌عسل", 0),
    ("رستوران بوف", 1),
    ("رستوران زنجیره‌ای بزرگ", 1),
    ("کافه نادری", 1),
    ("فست‌فود سون", 1),
    ("کافه گالری نگار", 1),
    ("بوتیک شیک‌پوش", 2),
    ("پوشاک پرسپولیس", 2),
    ("فروشگاه کفش ملی", 2),
    ("داروخانه دکتر دارو", 3),
    ("داروخانه ۱۳ آبان", 3),
    ("داروخانه شبانه‌روزی پاستور", 3),
    ("کلینیک دندانپزشکی سلامت", 4),
    ("آزمایشگاه پاتوبیولوژی پارس", 4),
    ("مرکز تصویربرداری پزشکی رازی", 4),
    ("پمپ بنزین شهید همت", 5),
    ("پمپ بنزین آزادی", 5),
    ("جایگاه سوخت پاسداران", 5),
    ("هتل پارسیان استقلال", 6),
    ("هتل آزادی تهران", 6),
    ("هتل اسپیناس پالاس", 6),
    ("اسنپ", 7),
    ("تپسی", 7),
    ("آژانس مسافرتی پرواز آسمان", 7),
    ("آژانس هواپیمایی ماهان", 7),
    ("آموزشگاه زبان ایران‌مهر", 8),
    ("مؤسسه کنکور گاج", 8),
    ("آموزشگاه فنی‌وحرفه‌ای سینا", 8),
    ("تعمیرگاه مرکزی سایپا", 9),
    ("نمایشگاه خودرو ایران‌خودرو", 9),
    ("خدمات فنی لوازم خانگی پارس", 9),
    ("فروشگاه لوازم خانگی الکترواستار", 10),
    ("دیجی استایل", 10),
    ("موبایل کام", 10),
    ("طلافروشی گوهر", 11),
    ("جواهری الماس درخشان", 11),
    ("شهرداری منطقه ۱ تهران", 12),
    ("بیمه ایران شعبه مرکزی", 12),
    ("بیمه پاسارگاد", 12),
    ("مؤسسه خیریه محک", 13),
    ("بنیاد کودک", 13),
    ("خیریه کهریزک", 13),
    ("دیجی‌کالا", 14),
    ("بامیلو", 14),
    ("ترب", 14),
    ("اسنپ مارکت", 14),
    ("فروشگاه اینترنتی مدیسه", 14),
]

CUSTOMER_POOL = [
    "هلدینگ تجاری گسترش پرداخت",
    "گروه مالی پرداخت نوین",
    "شرکت خدمات بازرگانی آسیا",
    "هلدینگ سرمایه‌گذاری پارس",
    "گروه فناوری پرداخت الکترونیک",
    "شرکت توسعه تجارت ایرانیان",
]

CITIES = ["تهران", "اصفهان", "مشهد", "شیراز", "تبریز", "کرج", "قم", "اهواز", "کرمان", "رشت"]

DAY_NAMES_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
MONTH_NAMES_EN = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]

STATUS_WEIGHTS = [("approved", 0.86), ("declined", 0.10), ("reversed", 0.04)]
CHANNELS = ["POS", "ONLINE", "MOBILE"]
TERMINAL_TYPES = ["POS", "mPOS", "Online"]

def months_ago(d: datetime.date, months: int) -> datetime.date:
    """Return the same calendar day N months earlier (clamped to month length)."""
    year = d.year
    month = d.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(d.day, [
        31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
    ][month - 1])
    return datetime.date(year, month, day)


# Rolling window: last 6 months through yesterday (dim_date, transactions, terminal installs)
MOCK_DATE_END = datetime.date.today() - datetime.timedelta(days=1)
MOCK_DATE_START = months_ago(MOCK_DATE_END, 6)


def weighted_choice(pairs):
    choices, weights = zip(*pairs)
    return random.choices(choices, weights=weights, k=1)[0]


def mask_pan():
    bin6 = random.choice(["603799", "589210", "627412", "627353", "636214", "502938"])
    last4 = f"{random.randint(0, 9999):04d}"
    return f"{bin6}******{last4}"


def build_database(n_transactions: int = 1000):
    # Prefer a clean file rebuild; if the DB is locked (e.g. uvicorn is running),
    # drop/recreate tables in place instead of deleting the file.
    if os.path.exists(SQLITE_PATH):
        try:
            os.remove(SQLITE_PATH)
        except OSError as e:
            print(f"Could not delete {SQLITE_PATH} ({e}); rebuilding tables in place.")
            Base.metadata.drop_all(engine)

    Base.metadata.create_all(engine)
    db = SessionLocal()

    try:
        # --- dim_date: rolling last 6 months through yesterday ---
        start = MOCK_DATE_START
        end = MOCK_DATE_END
        print(f"date window: {start.isoformat()} -> {end.isoformat()}")
        cur = start
        date_objs = []
        while cur <= end:
            dk = int(cur.strftime("%Y%m%d"))
            is_weekend = cur.weekday() in (3, 4)  # Thu/Fri as weekend (Iran-style)
            date_objs.append(DimDate(
                date_key=dk,
                full_date=cur,
                day_name=DAY_NAMES_FA[cur.weekday()],
                month_name=MONTH_NAMES_EN[cur.month - 1],
                year=cur.year,
                month=cur.month,
                day=cur.day,
                is_weekend=is_weekend,
                is_holiday=False,
            ))
            cur += datetime.timedelta(days=1)
        db.bulk_save_objects(date_objs)
        db.commit()
        print(f"dim_date: {len(date_objs)} rows")

        # --- dim_customer ---
        customers = []
        for i, name in enumerate(CUSTOMER_POOL, start=1):
            customers.append(DimCustomer(
                customer_name=name,
                access_key=f"demo-key-{i:03d}",
                role="admin" if i == 1 else "customer",
            ))
        db.add_all(customers)
        db.commit()
        customer_ids = [c.customer_id for c in customers]
        print(f"dim_customer: {len(customers)} rows")

        # --- dim_category: 15 Persian business verticals ---
        categories = []
        for i, name in enumerate(MERCHANT_CATEGORIES, start=1):
            categories.append(DimCategory(category_id=i, category_name=name))
        db.add_all(categories)
        db.commit()
        print(f"dim_category: {len(categories)} rows")

        # --- dim_merchant ---
        merchants = []
        for i, (name, cat_idx) in enumerate(MERCHANT_POOL, start=1):
            cat_id = cat_idx + 1
            cat_name = MERCHANT_CATEGORIES[cat_idx]
            merchants.append(DimMerchant(
                merchant_name=name,
                merchant_code=f"MER{i:05d}",
                mcc=CATEGORY_MCC[cat_idx],
                category_id=cat_id,
                category=cat_name,
                city=random.choice(CITIES),
                owner_customer_id=random.choice(customer_ids),
                is_active=True,
            ))
        db.add_all(merchants)
        db.commit()
        merchant_ids = [m.merchant_id for m in merchants]
        print(f"dim_merchant: {len(merchants)} rows")

        # --- dim_terminal: 2-5 terminals per merchant ---
        terminals = []
        for mid in merchant_ids:
            span_days = (end - start).days
            for _ in range(random.randint(2, 5)):
                install = start + datetime.timedelta(days=random.randint(0, span_days))
                terminals.append(DimTerminal(
                    terminal_serial=f"TRM{random.randint(100000, 999999)}",
                    merchant_id=mid,
                    terminal_type=random.choice(TERMINAL_TYPES),
                    install_date=install,
                    status=weighted_choice([("active", 0.92), ("inactive", 0.08)]),
                ))
        db.add_all(terminals)
        db.commit()
        terminal_rows = [(t.terminal_id, t.merchant_id) for t in terminals]
        print(f"dim_terminal: {len(terminals)} rows")

        # --- fact_transactions: ~1k rows ---
        date_keys = [d.date_key for d in date_objs]
        batch = []
        for i in range(n_transactions):
            term_id, merch_id = random.choice(terminal_rows)
            dk = random.choice(date_keys)
            d = datetime.datetime.strptime(str(dk), "%Y%m%d").date()
            tx_time = datetime.datetime.combine(
                d, datetime.time(random.randint(8, 23), random.randint(0, 59), random.randint(0, 59))
            )
            status = weighted_choice(STATUS_WEIGHTS)
            amount = round(random.lognormvariate(11.5, 1.2), 0)  # IRR-scale skewed amounts
            settlement = d + datetime.timedelta(days=1) if status == "approved" else d

            batch.append(FactTransaction(
                date_key=dk,
                terminal_id=term_id,
                merchant_id=merch_id,
                transaction_time=tx_time,
                amount=float(amount),
                currency="IRR",
                status=status,
                card_pan_masked=mask_pan(),
                response_code="00" if status == "approved" else random.choice(["05", "51", "61", "14"]),
                settlement_date=settlement,
                channel=random.choice(CHANNELS),
            ))

            if len(batch) >= 1000:
                db.bulk_save_objects(batch)
                db.commit()
                batch = []

        if batch:
            db.bulk_save_objects(batch)
            db.commit()

        print(f"fact_transactions: {n_transactions} rows")
        print("\nMock database built successfully at:", SQLITE_PATH)
        print("\nDemo customer access keys (use as X-Access-Key header / login):")
        for c in customers:
            try:
                print(f"  - {c.customer_name}: {c.access_key}  (role={c.role})")
            except UnicodeEncodeError:
                safe_name = c.customer_name.encode("ascii", errors="backslashreplace").decode("ascii")
                print(f"  - {safe_name}: {c.access_key}  (role={c.role})")

    finally:
        db.close()


if __name__ == "__main__":
    build_database(1000)
