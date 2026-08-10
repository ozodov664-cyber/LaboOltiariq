"""
LaboOltiariq bot — ma'lumotlar bazasi qatlami.
SQLite ishlatiladi (qo'shimcha server talab qilmaydi). Katta yuklama kutilsa,
shu funksiyalarni saqlab, ulanishni Postgres + SQLAlchemy'ga almashtirish mumkin.
"""
import sqlite3
import time
import random
import re
import datetime as _dt
from contextlib import contextmanager

import os

DB_PATH = os.environ.get("DB_PATH", "labooltiariq.db")
_db_dir = os.path.dirname(DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)  # masalan Railway'da DB_PATH=/app/data/labooltiariq.db bo'lsa, papka avtomatik yaratiladi


def _connect():
    # timeout + WAL: bot bir nechta foydalanuvchi so'rovini bir vaqtda qayta ishlaganda
    # ("database is locked" xatosining oldini olish uchun) muhim
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,          -- telegram user id
                role TEXT NOT NULL DEFAULT 'client',
                name TEXT,
                phone TEXT,
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS drivers (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                tariff TEXT NOT NULL DEFAULT 'kia_bort',
                pass TEXT NOT NULL,
                rating REAL NOT NULL DEFAULT 5.0,
                rating_count INTEGER NOT NULL DEFAULT 0,
                blocked INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'available',   -- available | busy | offline
                lat REAL,
                lng REAL,
                loc_updated_at INTEGER,
                sub_until INTEGER          -- obuna (haftalik/oylik to'lov) muddati tugaydigan vaqt (unix ts)
            );

            CREATE TABLE IF NOT EXISTS admin_ids (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL   -- 'admin' | 'dispatcher'
            );

            CREATE TABLE IF NOT EXISTS regions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                minimalka INTEGER NOT NULL,
                km_price INTEGER NOT NULL,
                wait_per_min INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tariffs (
                id TEXT PRIMARY KEY,                 -- masalan 'kia_bort', 'kia_tent', 'hyundai_bort', 'hyundai_tent'
                name TEXT NOT NULL,                  -- ko'rinadigan nomi, masalan 'Kia — Bort'
                mult REAL NOT NULL DEFAULT 1.0,       -- eski (koeffitsientga asoslangan) tizim qoldig'i, endi ishlatilmaydi
                car TEXT NOT NULL DEFAULT '',         -- mashina turi: 'Kia' | 'Hyundai'
                body TEXT NOT NULL DEFAULT '',        -- kuzov turi: 'bort' | 'tent'
                km_price INTEGER NOT NULL DEFAULT 0   -- shu mashina + kuzov turi uchun 1 km narxi (so'm)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES users(id),
                driver_id INTEGER REFERENCES users(id),
                region_id INTEGER NOT NULL REFERENCES regions(id),
                tariff_id TEXT NOT NULL REFERENCES tariffs(id),
                payment_method TEXT NOT NULL DEFAULT 'naqd',
                pickup_text TEXT,
                pickup_lat REAL,
                pickup_lng REAL,
                dest_text TEXT,
                dest_lat REAL,
                dest_lng REAL,
                est_km REAL NOT NULL DEFAULT 0,
                actual_km REAL NOT NULL DEFAULT 0,
                wait_seconds INTEGER NOT NULL DEFAULT 0,
                wait_price INTEGER NOT NULL DEFAULT 0,
                wait_started_at INTEGER,
                price INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'new',  -- new|accepted|in_progress|waiting|finished|cancelled
                rating INTEGER,
                created_at INTEGER,
                order_type TEXT NOT NULL DEFAULT 'app',  -- 'app' (ilova orqali) | 'street' (bordyurdan/yo'ldan) | 'phone' (dispetcher qo'lda qo'shgan)
                cancel_reason TEXT,
                phone_client_name TEXT,   -- telefon orqali qabul qilingan buyurtmalar uchun: mijoz ismi
                phone_client_phone TEXT   -- telefon orqali qabul qilingan buyurtmalar uchun: mijoz raqami
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        _migrate(conn)

        # Default settings (change these immediately after first deploy!)
        _ensure_setting(conn, "admin_password", "admin2026")
        _ensure_setting(conn, "dispatcher_password", "dispetcher2026")
        # Obuna narxlari — faqat ma'lumot uchun, admin panelda ko'rsatiladi (haqiqiy pul o'tkazilmaydi)
        _ensure_setting(conn, "sub_price_week", "150000")
        _ensure_setting(conn, "sub_price_month", "500000")

        # Eski (ekonom/komfort/biznes — koeffitsientga asoslangan) tariflar endi ishlatilmaydi:
        # narx endi mashina turi (Kia/Hyundai) va kuzov turi (bort/tent) bo'yicha belgilanadi.
        conn.execute("DELETE FROM tariffs WHERE id IN ('econom','comfort','business')")

        # Default mashina + kuzov turlari (narxlarni admin panelda — "🚗 Mashina narxlari" — o'zgartirish mumkin)
        for tid, name, car, body, km_price in [
            ("kia_bort", "Kia — Bort", "Kia", "bort", 1000),
            ("kia_tent", "Kia — Tent", "Kia", "tent", 2000),
            ("hyundai_bort", "Hyundai — Bort", "Hyundai", "bort", 1000),
            ("hyundai_tent", "Hyundai — Tent", "Hyundai", "tent", 2000),
            ("labo_bort", "Labo — Bort", "Labo", "bort", 1000),
            ("labo_tent", "Labo — Tent", "Labo", "tent", 2000),
        ]:
            conn.execute(
                # mult=1.0 shart emas (yangi bazalarda default bor), lekin eski bazalarda ushbu ustun
                # hali ham NOT NULL bo'lishi mumkin — shuning uchun har doim aniq qiymat beramiz.
                "INSERT OR IGNORE INTO tariffs (id, name, car, body, km_price, mult) VALUES (?,?,?,?,?,1.0)",
                (tid, name, car, body, km_price),
            )

        # Seed one region if none exists yet, so the bot is usable immediately
        row = conn.execute("SELECT COUNT(*) c FROM regions").fetchone()
        if row["c"] == 0:
            conn.execute(
                "INSERT INTO regions (name, minimalka, km_price, wait_per_min) VALUES (?,?,?,?)",
                ("Markaz", 15000, 2000, 1000),
            )


def _migrate(conn):
    """Eski bazalarni (yangi ustunlar qo'shilishidan oldin yaratilgan) xavfsiz yangilaydi.
    Har bir ALTER TABLE alohida sinaladi — ustun allaqachon bo'lsa xatolik e'tiborsiz qoldiriladi."""
    alters = [
        "ALTER TABLE drivers ADD COLUMN lat REAL",
        "ALTER TABLE drivers ADD COLUMN lng REAL",
        "ALTER TABLE drivers ADD COLUMN loc_updated_at INTEGER",
        "ALTER TABLE drivers ADD COLUMN sub_until INTEGER",
        "ALTER TABLE orders ADD COLUMN order_type TEXT NOT NULL DEFAULT 'app'",
        "ALTER TABLE orders ADD COLUMN cancel_reason TEXT",
        "ALTER TABLE orders ADD COLUMN phone_client_name TEXT",
        "ALTER TABLE orders ADD COLUMN phone_client_phone TEXT",
        "ALTER TABLE orders ADD COLUMN created_by INTEGER",
        "ALTER TABLE tariffs ADD COLUMN car TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE tariffs ADD COLUMN body TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE tariffs ADD COLUMN km_price INTEGER NOT NULL DEFAULT 0",
    ]
    for stmt in alters:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    conn.execute("CREATE TABLE IF NOT EXISTS admin_ids (user_id INTEGER PRIMARY KEY, role TEXT NOT NULL)")


def fmt_dt(ts):
    """Unix timestamp'ni o'qish uchun qulay sana-vaqtga aylantiradi."""
    if not ts:
        return "—"
    return _dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


def _ensure_setting(conn, key, default):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO settings (key, value) VALUES (?,?)", (key, default))


# ---------------- settings ----------------
def get_setting(key):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


# ---------------- users ----------------
def upsert_user(user_id, name=None, phone=None, role=None):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users (id, role, name, phone, created_at) VALUES (?,?,?,?,?)",
                (user_id, role or "client", name, phone, int(time.time())),
            )
        else:
            if name is not None:
                conn.execute("UPDATE users SET name=? WHERE id=?", (name, user_id))
            if phone is not None:
                conn.execute("UPDATE users SET phone=? WHERE id=?", (phone, user_id))
            if role is not None:
                conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))


def get_user(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None


# ---------------- telefon orqali murojaat qilgan mijozlar (doimiy saqlanadi) ----------------
def _phone_to_virtual_id(phone: str) -> int:
    """Telefon raqamidan barqaror, manfiy 'virtual mijoz' ID hosil qiladi. Manfiy bo'lgani
    uchun haqiqiy Telegram ID (har doim musbat) bilan hech qachon to'qnashmaydi, va bir xil
    raqam har doim bir xil ID beradi — shu sababli mijoz keyingi safar qo'ng'iroq qilganda
    ismi qayta so'ralmaydi, avtomatik topiladi."""
    digits = re.sub(r"\D", "", phone or "")
    n = int(digits[-9:]) if digits else 0
    return -(1_000_000_000 + n)


def get_phone_client_by_phone(phone):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (_phone_to_virtual_id(phone),)).fetchone()
        return dict(row) if row else None


def upsert_phone_client(name, phone):
    """Telefon orqali murojaat qilgan mijozni bazaga doimiy saqlaydi (yoki ismini yangilaydi)
    va doimiy 'virtual' ID qaytaradi. Shu ID buyurtmaning client_id maydonida ishlatiladi —
    dispetcherning o'z Telegram ID'sidan butunlay mustaqil, shuning uchun dispetcher o'zi
    shaxsiy mijoz sifatida taksi chaqirsa ham hech qanday to'qnashuv bo'lmaydi."""
    vid = _phone_to_virtual_id(phone)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (id, role, name, phone, created_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, phone=excluded.phone",
            (vid, "phone_client", name, phone, int(time.time())),
        )
    return vid


# ---------------- drivers ----------------
def create_driver(user_id, tariff, password, name=None, phone=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (id, role, name, phone, created_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET role=excluded.role, name=excluded.name, phone=excluded.phone",
            (user_id, "driver", name, phone, int(time.time())),
        )
        conn.execute(
            "INSERT INTO drivers (user_id, tariff, pass) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET tariff=excluded.tariff, pass=excluded.pass",
            (user_id, tariff, password),
        )


def get_driver(user_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT u.id, u.name, u.phone, d.* FROM drivers d JOIN users u ON u.id=d.user_id WHERE d.user_id=?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def list_drivers():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT u.id, u.name, u.phone, d.* FROM drivers d JOIN users u ON u.id=d.user_id ORDER BY u.name"
        ).fetchall()
        return [dict(r) for r in rows]


def list_available_drivers(tariff_id):
    """Faqat: bloklanmagan, onlayn VA obunasi faol (to'lov qilingan) haydovchilar buyurtma oladi."""
    now = int(time.time())
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT u.id, u.name, u.phone, d.* FROM drivers d JOIN users u ON u.id=d.user_id "
            "WHERE d.tariff=? AND d.blocked=0 AND d.status='available' "
            "AND d.sub_until IS NOT NULL AND d.sub_until > ?",
            (tariff_id, now),
        ).fetchall()
        return [dict(r) for r in rows]


def driver_subscription_active(driver: dict) -> bool:
    return bool(driver.get("sub_until")) and driver["sub_until"] > int(time.time())


def set_driver_location(user_id, lat, lng):
    with get_conn() as conn:
        conn.execute(
            "UPDATE drivers SET lat=?, lng=?, loc_updated_at=? WHERE user_id=?",
            (lat, lng, int(time.time()), user_id),
        )


def list_drivers_with_location():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT u.id, u.name, u.phone, d.* FROM drivers d JOIN users u ON u.id=d.user_id "
            "WHERE d.lat IS NOT NULL AND d.lng IS NOT NULL ORDER BY d.loc_updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def extend_driver_subscription(user_id, days):
    """To'lovni qayd etadi: obuna muddatini (joriy muddat tugamagan bo'lsa — undan, aks holda hozirdan)
    berilgan kun soniga uzaytiradi. Yangi muddatni (unix ts) qaytaradi."""
    now = int(time.time())
    with get_conn() as conn:
        row = conn.execute("SELECT sub_until FROM drivers WHERE user_id=?", (user_id,)).fetchone()
        base = row["sub_until"] if row and row["sub_until"] and row["sub_until"] > now else now
        new_until = base + days * 86400
        conn.execute("UPDATE drivers SET sub_until=? WHERE user_id=?", (new_until, user_id))
        return new_until


def set_driver_status(user_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE drivers SET status=? WHERE user_id=?", (status, user_id))


def set_driver_blocked(user_id, blocked):
    with get_conn() as conn:
        conn.execute("UPDATE drivers SET blocked=? WHERE user_id=?", (1 if blocked else 0, user_id))


def set_driver_password(user_id, password):
    with get_conn() as conn:
        conn.execute("UPDATE drivers SET pass=? WHERE user_id=?", (password, user_id))


def add_driver_rating(user_id, stars):
    with get_conn() as conn:
        row = conn.execute("SELECT rating, rating_count FROM drivers WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return
        new_count = row["rating_count"] + 1
        new_rating = ((row["rating"] * row["rating_count"]) + stars) / new_count
        conn.execute(
            "UPDATE drivers SET rating=?, rating_count=? WHERE user_id=?", (new_rating, new_count, user_id)
        )


def gen_driver_password():
    return str(random.randint(1000, 9999))


# ---------------- regions ----------------
def list_regions():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM regions ORDER BY name").fetchall()]


def get_region(region_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM regions WHERE id=?", (region_id,)).fetchone()
        return dict(row) if row else None


def add_region(name, minimalka, km_price, wait_per_min):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO regions (name, minimalka, km_price, wait_per_min) VALUES (?,?,?,?)",
            (name, minimalka, km_price, wait_per_min),
        )


def delete_region(region_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM regions WHERE id=?", (region_id,))


# ---------------- tariffs ----------------
def list_tariffs():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM tariffs ORDER BY car, body").fetchall()]


def get_tariff(tariff_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tariffs WHERE id=?", (tariff_id,)).fetchone()
        return dict(row) if row else None


def set_tariff_price(tariff_id, km_price):
    with get_conn() as conn:
        conn.execute("UPDATE tariffs SET km_price=? WHERE id=?", (km_price, tariff_id))


# ---------------- orders ----------------
def create_order(client_id, region_id, tariff_id, payment_method, pickup_text, pickup_lat, pickup_lng,
                  dest_text, dest_lat, dest_lng, est_km, price, order_type="app",
                  phone_client_name=None, phone_client_phone=None, created_by=None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO orders (client_id, region_id, tariff_id, payment_method, pickup_text, pickup_lat, "
            "pickup_lng, dest_text, dest_lat, dest_lng, est_km, price, status, created_at, order_type, "
            "phone_client_name, phone_client_phone, created_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'new', ?, ?, ?, ?, ?)",
            (client_id, region_id, tariff_id, payment_method, pickup_text, pickup_lat, pickup_lng,
             dest_text, dest_lat, dest_lng, est_km, price, int(time.time()), order_type,
             phone_client_name, phone_client_phone, created_by),
        )
        return cur.lastrowid


def get_order(order_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        return dict(row) if row else None


def get_active_order_for_client(client_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE client_id=? AND status IN ('new','accepted','in_progress','waiting') "
            "ORDER BY created_at DESC LIMIT 1",
            (client_id,),
        ).fetchone()
        return dict(row) if row else None


def get_active_order_for_driver(driver_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE driver_id=? AND status IN ('accepted','in_progress','waiting') "
            "ORDER BY created_at DESC LIMIT 1",
            (driver_id,),
        ).fetchone()
        return dict(row) if row else None


def accept_order(order_id, driver_id):
    """Atomically assign a driver only if the order is still unclaimed. Returns True on success."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE orders SET driver_id=?, status='accepted' WHERE id=? AND status='new'",
            (driver_id, order_id),
        )
        return cur.rowcount == 1


def set_order_status(order_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))


def start_trip(order_id):
    """Safar boshlanganda actual_km mijozga aytilgan taxminiy masofaga (est_km) tenglashtiriladi.
    Narx mijozga buyurtma berishda ko'rsatilgan FINAL narx — safar davomida (GPS orqali ham,
    qo'lda ham) endi qayta hisoblanmaydi, faqat "kutish" (wait_price) alohida qo'shiladi."""
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status='in_progress', actual_km=est_km WHERE id=?", (order_id,))


def add_km(order_id, km_delta, new_price):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET actual_km = actual_km + ?, price=? WHERE id=?", (km_delta, new_price, order_id)
        )


def start_waiting(order_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status='waiting', wait_started_at=? WHERE id=?", (int(time.time()), order_id)
        )


def stop_waiting(order_id, added_seconds, added_price, new_total_price):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status='in_progress', wait_seconds = wait_seconds + ?, "
            "wait_price = wait_price + ?, price=?, wait_started_at=NULL WHERE id=?",
            (added_seconds, added_price, new_total_price, order_id),
        )


def finish_order(order_id):
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status='finished' WHERE id=?", (order_id,))


def cancel_order(order_id):
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))


def cancel_order_by_client(order_id, client_id):
    """Mijoz faqat hali qabul qilinmagan yoki hali yo'lga chiqilmagan buyurtmani bekor qila oladi."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE orders SET status='cancelled', cancel_reason='client' "
            "WHERE id=? AND client_id=? AND status IN ('new','accepted')",
            (order_id, client_id),
        )
        return cur.rowcount == 1


def get_orders_for_client(client_id, limit=10):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE client_id=? ORDER BY created_at DESC LIMIT ?", (client_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------- admin/dispatcher registry (persisted, for broadcasts/SOS) ----------------
def add_admin_id(user_id, role):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO admin_ids (user_id, role) VALUES (?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET role=excluded.role",
            (user_id, role),
        )


def list_admin_ids(role=None):
    with get_conn() as conn:
        if role:
            rows = conn.execute("SELECT * FROM admin_ids WHERE role=?", (role,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM admin_ids").fetchall()
        return [dict(r) for r in rows]


def rate_order(order_id, stars):
    with get_conn() as conn:
        conn.execute("UPDATE orders SET rating=? WHERE id=?", (stars, order_id))


def list_recent_orders(limit=20):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def list_active_orders():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE status IN ('new','accepted','in_progress','waiting') ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def revenue_stats():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) trips, COALESCE(SUM(price),0) revenue FROM orders WHERE status='finished'"
        ).fetchone()
        return dict(row)


def driver_trip_stats(driver_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) trips, COALESCE(SUM(price),0) revenue FROM orders WHERE driver_id=? AND status='finished'",
            (driver_id,),
        ).fetchone()
        return dict(row)
