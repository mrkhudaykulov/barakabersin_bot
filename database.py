import re
import os
import logging


# ═══════════════════════════════════════
# BAZA ULANGANLIK
# ═══════════════════════════════════════

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """PostgreSQL yoki SQLite — qaysi biri bor bo'lsa"""
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    else:
        import sqlite3
        return sqlite3.connect("chorva.db")


def get_placeholder():
    """SQL placeholder — PostgreSQL %s, SQLite ?"""
    return "%s" if DATABASE_URL else "?"


# ═══════════════════════════════════════
# ⚠️ Chegaralar

MAX_PRICE = 50_000_000
MIN_PRICE = 50_000

# Эълон стандарт муддати (кун)
AD_EXPIRE_DAYS = 7

# ═══════════════════════════════════════
# БАЗА ЯРАТИШ
# ═══════════════════════════════════════

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        # ═══ POSTGRESQL ═══
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                msg_id TEXT,
                animal_type TEXT,
                quantity TEXT,
                price TEXT,
                description TEXT,
                region TEXT,
                district TEXT,
                mfy TEXT,
                phone TEXT,
                username TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_by BIGINT,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '10 days')
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                phone TEXT,
                full_name TEXT,
                username TEXT,
                region TEXT,
                district TEXT,
                mfy TEXT,
                rejection_count INTEGER DEFAULT 0,
                is_blocked BOOLEAN DEFAULT FALSE,
                blocked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_prices (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                animal_type TEXT NOT NULL,
                region TEXT NOT NULL,
                price INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                animal_type TEXT NOT NULL,
                region TEXT NOT NULL,
                district TEXT DEFAULT 'Барчаси',
                min_price BIGINT,
                max_price BIGINT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # 🔥 PostgreSQL учун янги медиа жадвали
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ad_media (
                id SERIAL PRIMARY KEY,
                ad_id INTEGER,
                media_type TEXT, -- 'photo' ёки 'video'
                file_id TEXT,
                FOREIGN KEY (ad_id) REFERENCES ads (id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_review_messages (
                ad_id INTEGER NOT NULL,
                admin_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                PRIMARY KEY (ad_id, admin_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vet_suggestions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                action_type TEXT NOT NULL,
                region TEXT NOT NULL,
                district TEXT NOT NULL,
                role_type TEXT NOT NULL,
                fish TEXT,
                lavozim TEXT,
                tel TEXT,
                comment TEXT,
                status TEXT DEFAULT 'pending',
                admin_id BIGINT,
                admin_comment TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                reviewed_at TIMESTAMP
            )
        """)

    

    else:
        # ═══ SQLITE (lokal test uchun) ═══
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                msg_id TEXT,
                animal_type TEXT,
                quantity TEXT,
                price TEXT,
                description TEXT,
                region TEXT,
                district TEXT,
                mfy TEXT,
                phone TEXT,
                username TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP DEFAULT (datetime('now', '+10 days'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone TEXT,
                full_name TEXT,
                username TEXT,
                region TEXT,
                district TEXT,
                mfy TEXT,
                rejection_count INTEGER DEFAULT 0,
                is_blocked INTEGER DEFAULT 0,
                blocked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                animal_type TEXT NOT NULL,
                region TEXT NOT NULL,
                price INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                animal_type TEXT,
                region TEXT,
                district TEXT DEFAULT 'Барчаси',
                min_price INTEGER,
                max_price INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 🔥 SQLite учун янги медиа жадвали
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ad_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_id INTEGER,
                media_type TEXT,
                file_id TEXT,
                FOREIGN KEY (ad_id) REFERENCES ads (id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_review_messages (
                ad_id INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                PRIMARY KEY (ad_id, admin_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vet_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                action_type TEXT NOT NULL,
                region TEXT NOT NULL,
                district TEXT NOT NULL,
                role_type TEXT NOT NULL,
                fish TEXT,
                lavozim TEXT,
                tel TEXT,
                comment TEXT,
                status TEXT DEFAULT 'pending',
                admin_id INTEGER,
                admin_comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP
            )
        """)

    conn.commit()
    conn.close()

    # Мавжуд базани янги устунлар билан янгилаш
    migrate_db()

    logging.info(
        "Baza yaratildi (PostgreSQL)" if DATABASE_URL
        else "Baza yaratildi (SQLite)"
    )


def migrate_db():
    """
    Мавжуд базага янги устунларни хавфсиз қўшиш.
    Бот аллақачон ишлаётган бўлса ҳам хатосиз ишлайди.
    """
    conn = get_connection()
    cursor = conn.cursor()

    migrations = []

    if DATABASE_URL:
        # ═══ PostgreSQL migrations ═══
        migrations = [
            # ads жадвали
            "ALTER TABLE ads ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE ads ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '7 days')",
            "UPDATE ads SET created_at = NOW() WHERE created_at IS NULL",
            # users жадвали
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS unique_notification",
            "ALTER TABLE notifications ADD CONSTRAINT unique_notification UNIQUE (user_id, animal_type, region, district, min_price, max_price)",            
            "ALTER TABLE ads ADD COLUMN IF NOT EXISTS reviewed_by BIGINT",
            "ALTER TABLE ads ADD COLUMN IF NOT EXISTS price_display TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS rejection_count INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS region TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS district TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfy TEXT",
            "ALTER TABLE ads ALTER COLUMN expires_at SET DEFAULT (NOW() + INTERVAL '7 days')",            
            "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS district TEXT DEFAULT 'Барчаси'",
            """CREATE TABLE IF NOT EXISTS admin_review_messages (
                ad_id INTEGER NOT NULL, admin_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL, chat_id BIGINT NOT NULL,
                PRIMARY KEY (ad_id, admin_id)
            )""",
            """CREATE TABLE IF NOT EXISTS vet_suggestions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                action_type TEXT NOT NULL,
                region TEXT NOT NULL,
                district TEXT NOT NULL,
                role_type TEXT NOT NULL,
                fish TEXT,
                lavozim TEXT,
                tel TEXT,
                comment TEXT,
                status TEXT DEFAULT 'pending',
                admin_id BIGINT,
                admin_comment TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                reviewed_at TIMESTAMP
            )"""
            
        ]
        for sql in migrations:
            try:
                cursor.execute(sql)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logging.debug(f"Migration (skipped): {e}")

    else:
        # ═══ SQLite migrations — try/except bilan ═══
        sqlite_migrations = [
            "ALTER TABLE ads ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE ads ADD COLUMN expires_at TIMESTAMP DEFAULT (datetime('now', '+10 days'))",
            "UPDATE ads SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL",
            "ALTER TABLE users ADD COLUMN phone TEXT",
            "ALTER TABLE users ADD COLUMN full_name TEXT",
            "ALTER TABLE users ADD COLUMN username TEXT",
            "ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",                  
            "ALTER TABLE ads ADD COLUMN reviewed_by INTEGER",
            "ALTER TABLE ads ADD COLUMN price_display TEXT",
            "ALTER TABLE users ADD COLUMN rejection_count INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN blocked_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN region TEXT",
            "ALTER TABLE users ADD COLUMN district TEXT",
            "ALTER TABLE users ADD COLUMN mfy TEXT",
            "ALTER TABLE notifications ADD COLUMN district TEXT DEFAULT 'Барчаси'",
            """CREATE TABLE IF NOT EXISTS admin_review_messages (
                ad_id INTEGER NOT NULL, admin_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
                PRIMARY KEY (ad_id, admin_id)
            )""",
            """CREATE TABLE IF NOT EXISTS vet_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                action_type TEXT NOT NULL,
                region TEXT NOT NULL,
                district TEXT NOT NULL,
                role_type TEXT NOT NULL,
                fish TEXT,
                lavozim TEXT,
                tel TEXT,
                comment TEXT,
                status TEXT DEFAULT 'pending',
                admin_id INTEGER,
                admin_comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP
            )"""
        ]
        for sql in sqlite_migrations:
            try:
                cursor.execute(sql)
                conn.commit()
            except Exception:                
                pass

    conn.close()
    logging.info("Миграция тугади.")

# ═══════════════════════════════════════
# 🔥 ЭЪЛОН ВА МЕДИАЛАРНИ БАЗАГА САҚЛАШФУНКЦИЯСИ
# ═══════════════════════════════════════

def save_ad_with_media(user_id: int, data: dict, media_list: list) -> int | None:
    """
    Эълон малумотларини 'ads' жадвалига қўшади ва унга тегишли
    барча расм/видеоларни 'ad_media' жадвалига боғлаб сақлайди.
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Эълон матнини ва малумотларини сақлаш
        cursor.execute(f"""
            INSERT INTO ads (user_id, animal_type, quantity, price, description, region, district, mfy, phone, username, status)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, 'pending')
        """, (
            user_id, data.get('animal_type'), data.get('quantity'), data.get('price'),
            data.get('description'), data.get('region'), data.get('district'), data.get('mfy'),
            data.get('phone'), data.get('username')
        ))
        
        # Янги яратилган эълоннинг ID сини оламиз
        ad_id = cursor.lastrowid
        
        # Агар SQLite бўлса ва lastrowid ўхшамаса, муқобил вариант:
        if not ad_id and not DATABASE_URL:
            cursor.execute("SELECT last_insert_rowid()")
            ad_id = cursor.fetchone()[0]

        # 2. Агар media_list ичида файллар бўлса, уларни айлантириб базага ёзиш
        if media_list and ad_id:
            for media in media_list:
                cursor.execute(f"""
                    INSERT INTO ad_media (ad_id, media_type, file_id)
                    VALUES ({p}, {p}, {p})
                """, (ad_id, media.get('type'), media.get('file_id')))
                
        conn.commit()
        return ad_id  # Муваффақиятли бўлса ID қайтади
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Базага эълон ва медиани сақлашда хатолик: {e}")
        return None
    finally:
        conn.close()


# ═══════════════════════════════════════
# ФОЙДАЛАНУВЧИ — ТЕЛЕФОН САҚЛАШ
# ═══════════════════════════════════════

def save_user(user_id: int, full_name: str = None, username: str = None, phone: str = None,
              region: str = None, district: str = None, mfy: str = None):
    """Фойдаланувчини базага сақлаш ёки янгилаш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute(f"""
            INSERT INTO users (user_id, full_name, username, phone, region, district, mfy)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
            ON CONFLICT (user_id) DO UPDATE SET
                full_name = COALESCE(EXCLUDED.full_name, users.full_name),
                username  = COALESCE(EXCLUDED.username, users.username),
                phone     = COALESCE(EXCLUDED.phone, users.phone),
                region    = COALESCE(EXCLUDED.region, users.region),
                district  = COALESCE(EXCLUDED.district, users.district),
                mfy       = COALESCE(EXCLUDED.mfy, users.mfy)
        """, (user_id, full_name, username, phone, region, district, mfy))
    else:
        cursor.execute(f"""
            INSERT OR IGNORE INTO users (user_id, full_name, username, phone, region, district, mfy)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
        """, (user_id, full_name, username, phone, region, district, mfy))

        # Мавжуд фойдаланувчини янгилаш
        if full_name:
            cursor.execute(f"UPDATE users SET full_name = {p} WHERE user_id = {p}", (full_name, user_id))
        if username:
            cursor.execute(f"UPDATE users SET username = {p} WHERE user_id = {p}", (username, user_id))
        if phone:
            cursor.execute(f"UPDATE users SET phone = {p} WHERE user_id = {p}", (phone, user_id))
        if region:
            cursor.execute(f"UPDATE users SET region = {p} WHERE user_id = {p}", (region, user_id))
        if district:
            cursor.execute(f"UPDATE users SET district = {p} WHERE user_id = {p}", (district, user_id))
        if mfy:
            cursor.execute(f"UPDATE users SET mfy = {p} WHERE user_id = {p}", (mfy, user_id))

    conn.commit()
    conn.close()


def get_user_profile(user_id: int) -> dict:
    """
    Фойдаланувчининг сақланган профилини қайтаради:
    {'phone', 'region', 'district', 'mfy'} — ҳар бири None бўлиши мумкин.
    Mini App'да авто-тўлдириш учун ишлатилади.
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT phone, region, district, mfy FROM users WHERE user_id = {p}",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {"phone": None, "region": None, "district": None, "mfy": None}
    phone, region, district, mfy = row
    return {"phone": phone, "region": region, "district": district, "mfy": mfy}


def get_user_phone(user_id: int) -> str | None:
    """Базадан фойдаланувчи телефонини олиш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT phone FROM users WHERE user_id = {p}", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


# ═══════════════════════════════════════
# ЭЪЛОН МУДДАТИ — SCHEDULER УЧУН
# ═══════════════════════════════════════

def get_expiring_ads(days_left: int):
    """
    Муддати days_left кун қолган АКТИВ эълонларни қайтаради.
    Scheduler эслатма юборади.
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute(f"""
            SELECT id, user_id, animal_type, quantity, price, msg_id
            FROM ads
            WHERE status = {p}
              AND expires_at IS NOT NULL
              AND expires_at::date = (NOW() + INTERVAL '{days_left} days')::date
        """, ("active",))
    else:
        cursor.execute(f"""
            SELECT id, user_id, animal_type, quantity, price, msg_id
            FROM ads
            WHERE status = {p}
              AND expires_at IS NOT NULL
              AND date(expires_at) = date('now', '+{days_left} days')
        """, ("active",))

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_expired_ads():
    """
    Муддати ўтган (expires_at < now) АКТИВ эълонларни қайтаради.
    Scheduler архивлаши учун.
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute(f"""
            SELECT id, user_id, animal_type, msg_id
            FROM ads
            WHERE status = {p}
              AND expires_at IS NOT NULL
              AND expires_at < NOW()
        """, ("active",))
    else:
        cursor.execute(f"""
            SELECT id, user_id, animal_type, msg_id
            FROM ads
            WHERE status = {p}
              AND expires_at IS NOT NULL
              AND expires_at < datetime('now')
        """, ("active",))

    rows = cursor.fetchall()
    conn.close()
    return rows


def archive_ad(ad_id: int):
    """Эълонни arxiv статусига ўтказиш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE ads SET status = 'expired' WHERE id = {p}",
        (ad_id,)
    )
    conn.commit()
    conn.close()


def repost_ad(ad_id: int):
    """Эълонни каналга қайта жойлаш — expires_at 7 кунга янгиланади"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"""
            UPDATE ads
            SET expires_at = NOW() + INTERVAL '7 days',
                status = 'active'
            WHERE id = {p}
        """, (ad_id,))
    else:
        cursor.execute(f"""
            UPDATE ads
            SET expires_at = datetime('now', '+7 days'),
                status = 'active'
            WHERE id = {p}
        """, (ad_id,))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════

KEYBOARD_FIX = {
    "Күкөр": "Қўчқор",
    "Күчи": "Қўзи",
    "Кукkop": "Қўчқор",
    "Бузoк": "Бузоқ",
    "Сoвлик": "Совлиқ",
    "Улoк": "Улоқ",
    "Кашкадаре": "Қашқадарё",
    "Кашкадарё": "Қашқадарё",
    "Сурхондаре": "Сурхондарё",
    "Сурхондарё": "Сурхондарё",
    "Сирдаре": "Сирдарё",
    "Сирдарё": "Сирдарё",
    "Тошқент": "Тошкент",
    "Коракалпоғистон": "Қорақалпоғистон",
    "Кўп": "Қўй",
    "Кўq": "Қўй",
    "Кyка/Сигир": "Буқа/Сигир",
    "Бapчаси": "Барчаси",
}


def fix_keyboard_text(text):
    """Клавиатуралардан келган матнни базага мослаш"""
    if not text:
        return text
    if text in KEYBOARD_FIX:
        return KEYBOARD_FIX[text]
    return text


def parse_price_text(text):
    """Матндаги нархни рақамга айлантириш"""
    text = str(text).lower().strip()

    for word in ['сўм', "so'm", 'сум', 'sum', 'сом', 'som']:
        text = text.replace(word, '')
    text = text.strip()

    million_words = [
        'млн', 'миллиoн', 'миллион', 'милион', 'милйон', 'милиён', 'милийон',
        'млён', 'млион', 'милон', 'million', 'milion', 'milyon', 'mln'
    ]
    for word in million_words:
        if word in text:
            num_part = text.replace(word, '').strip()
            num_part = num_part.replace(',', '.').replace(' ', '')
            try:
                return int(float(num_part) * 1_000_000)
            except ValueError:
                continue

    thousand_words = ['минг', 'миг', 'мин', 'миң', 'ming']
    for word in thousand_words:
        if word in text:
            num_part = text.replace(word, '').strip()
            num_part = num_part.replace(',', '.').replace(' ', '')
            try:
                return int(float(num_part) * 1_000)
            except ValueError:
                continue

    text_clean = text.replace(',', '.').strip()

    if '.' in text_clean:
        parts = text_clean.split('.')
        digits_only = all(p.strip().isdigit() for p in parts if p.strip())
        if digits_only and len(parts) == 2:
            try:
                num = float(text_clean)
                if num < 50:
                    return int(num * 1_000_000)
            except ValueError:
                pass

    cleaned = ''.join(c for c in text if c.isdigit())
    if not cleaned:
        return 0
    result = int(cleaned)
    if result < 50:
        result *= 1_000_000
    return result



def fmt_number(n):
    """Рақамни форматда кўрсатиш: 15 000 000"""
    return f"{n:,.0f}".replace(",", " ")

def parse_price_with_type(text):
    if not text:
        return 0, "аниқ"

    clean = str(text).lower().strip()

    per_unit_variants = [
        "дан", "dan",
        "доная", "доноси", "донадан",
        "ҳар бири", "хар бири", "харбир",
        "тарадан",
    ]

    is_per_unit = False
    for variant in per_unit_variants:
        if variant in clean:
            is_per_unit = True
            clean = clean.replace(variant, "").strip()
            break

    price = parse_price_text(clean)
    price_type = "дан" if is_per_unit else "аниқ"

    return price, price_type


# ═══════════════════════════════════════
# НАРХ ИНДЕКСИ
# ═══════════════════════════════════════

def get_price_index(animal_type=None):
    """Эълонлар асосида нархлар индексини ҳисоблаш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    query = f"""
        SELECT animal_type, region, price
        FROM ads
        WHERE status = {p}
    """
    params = ["active"]
    if animal_type:
        query += f" AND animal_type = {p}"
        params.append(animal_type)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    stats = {}
    for a_type, region, price_text in rows:
        price = parse_price_text(price_text)
        if price == 0 or price > MAX_PRICE:
            continue
        key = (a_type, region)
        if key not in stats:
            stats[key] = {"prices": [], "count": 0}
        stats[key]["prices"].append(price)
        stats[key]["count"] += 1

    result = {}
    for (a_type, region), data in stats.items():
        if a_type not in result:
            result[a_type] = []
        prices = data["prices"]
        result[a_type].append({
            "region": region,
            "avg": sum(prices) / len(prices),
            "min": min(prices),
            "max": max(prices),
            "count": data["count"]
        })

    for a_type in result:
        result[a_type].sort(key=lambda x: x["avg"])

    return result


def get_market_prices_index():
    """Фойдаланувчилар киритган бозор нархлари"""
    conn = get_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute("""
            SELECT animal_type, region,
                   AVG(price) as avg_price,
                   MIN(price) as min_price,
                   MAX(price) as max_price,
                   COUNT(*) as cnt
            FROM market_prices
            WHERE created_at > NOW() - INTERVAL '10 days'
            GROUP BY animal_type, region
            ORDER BY animal_type, avg_price
        """)
    else:
        cursor.execute("""
            SELECT animal_type, region,
                   AVG(price) as avg_price,
                   MIN(price) as min_price,
                   MAX(price) as max_price,
                   COUNT(*) as cnt
            FROM market_prices
            WHERE created_at > datetime('now', '-10 days')
            GROUP BY animal_type, region
            ORDER BY animal_type, avg_price
        """)

    rows = cursor.fetchall()
    conn.close()

    result = {}
    for a_type, region, avg_p, min_p, max_p, cnt in rows:
        if avg_p > MAX_PRICE:
            continue
        if a_type not in result:
            result[a_type] = []
        result[a_type].append({
            "region": region,
            "avg": avg_p,
            "min": min_p,
            "max": max_p,
            "count": cnt
        })

    return result


def search_ads_db(animal_type=None, region=None, district=None, max_price=None, limit=10):
    """Эълонларни қидириш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    query = f"""
        SELECT id, animal_type, quantity, price,
               region, district, description
        FROM ads
        WHERE status = {p}
    """
    params = ["active"]

    if animal_type:
        query += f" AND animal_type = {p}"
        params.append(animal_type)
    if region:
        query += f" AND region = {p}"
        params.append(region)
    if district:
        query += f" AND district = {p}"
        params.append(district)

    query += f" ORDER BY id DESC LIMIT {p}"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    if max_price:
        filtered = []
        for row in rows:
            price = parse_price_text(row[3])
            if price > 0 and price <= max_price:
                filtered.append(row)
        return filtered

    return rows


# ═══════════════════════════════════════
# ҚИДИРИШ (3 МАНБА)
# ═══════════════════════════════════════

def search_all(animal_type=None, region=None, district=None, limit=10):
    """3 манбадан қидириш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    result = {"ads": [], "market_prices": [], "stats": {}}

    # ═══ Эълонлар ═══
    query_ads = f"""
        SELECT id, animal_type, region, price,
               district, description, quantity, user_id, msg_id
        FROM ads
        WHERE status = {p}
    """
    params_ads = ["active"]
    if animal_type:
        query_ads += f" AND animal_type = {p}"
        params_ads.append(animal_type)
    if region:
        query_ads += f" AND region = {p}"
        params_ads.append(region)
    if district:
        query_ads += f" AND district = {p}"
        params_ads.append(district)
    query_ads += f" ORDER BY id DESC LIMIT {p}"
    params_ads.append(limit)
    cursor.execute(query_ads, params_ads)
    result["ads"] = cursor.fetchall()

    # ═══ Бозор нархлари ═══
    query_mp = """
        SELECT animal_type, region, price, created_at
        FROM market_prices WHERE 1=1
    """
    params_mp = []
    if animal_type:
        query_mp += f" AND animal_type = {p}"
        params_mp.append(animal_type)
    if region:
        query_mp += f" AND region = {p}"
        params_mp.append(region)
    query_mp += " ORDER BY created_at DESC LIMIT 100"
    cursor.execute(query_mp, params_mp)
    result["market_prices"] = cursor.fetchall()

    conn.close()

    # ═══ Статистика ═══
    all_prices = []
    for ad in result["ads"]:
        price = parse_price_text(ad[3])
        if MIN_PRICE <= price <= MAX_PRICE:
            all_prices.append(price)
    for mp in result["market_prices"]:
        if MIN_PRICE <= mp[2] <= MAX_PRICE:
            all_prices.append(mp[2])

    if all_prices:
        result["stats"] = {
            "count": len(all_prices),
            "avg": sum(all_prices) / len(all_prices),
            "min": min(all_prices),
            "max": max(all_prices)
        }

    return result


# ═══════════════════════════════════════
# СТАТИСТИКА
# ═══════════════════════════════════════

def get_full_statistics():
    """Тўлиқ статистика"""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM ads")
    stats["total_ads"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM ads WHERE status='active'")
    stats["active_ads"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM ads WHERE status='sold'")
    stats["sold_ads"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    stats["total_users"] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT animal_type, COUNT(*) as cnt
        FROM ads WHERE status='active'
        GROUP BY animal_type ORDER BY cnt DESC
    """)
    stats["by_animal"] = cursor.fetchall()

    cursor.execute("""
        SELECT region, COUNT(*) as cnt
        FROM ads WHERE status='active'
        GROUP BY region ORDER BY cnt DESC
    """)
    stats["by_region"] = cursor.fetchall()

    cursor.execute("SELECT animal_type, price FROM ads WHERE status='active'")
    raw_prices = cursor.fetchall()

    price_by_animal = {}
    for a_type, price_text in raw_prices:
        price = parse_price_text(price_text)
        if MIN_PRICE <= price <= MAX_PRICE:
            if a_type not in price_by_animal:
                price_by_animal[a_type] = []
            price_by_animal[a_type].append(price)

    stats["avg_prices"] = {}
    for a_type, prices in price_by_animal.items():
        stats["avg_prices"][a_type] = {
            "avg": sum(prices) / len(prices),
            "min": min(prices),
            "max": max(prices),
            "count": len(prices)
        }

    cursor.execute("SELECT COUNT(*) FROM market_prices")
    stats["market_price_entries"] = cursor.fetchone()[0]

    conn.close()
    return stats


# ═══════════════════════════════════════
# МАН ЭТИЛГАН СЎЗЛАР
# ═══════════════════════════════════════

BAD_WORDS = [
    "кахба", "ҷалоб", "ғашт", "нарас",
    "шалоп", "ғашак", "юзлик",
    "ҳули", "сик", "пиз",
    "қўтоқ", "қўтақ", "сикаман",
    "секс", "пиздес", "пиздец", "далбан",
    "далбаёп", "хуйет", "хует", "ташақ",
    "аминга", "нахуй", "наххуй",
]


def normalize_word(word):
    """Bitta so'zni tekshirishga tayyorlash"""
    if not word:
        return ""
    word = word.lower().strip()
    word = re.sub(r'(.)\1{2,}', r'\1', word)

    latin_to_cyrillic = {
        'a': 'а', 'b': 'б', 'c': 'с', 'd': 'д', 'e': 'е',
        'f': 'ф', 'g': 'г', 'h': 'х', 'i': 'и', 'j': 'ж',
        'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о',
        'p': 'п', 'q': 'қ', 'r': 'р', 's': 'с', 't': 'т',
        'u': 'у', 'v': 'в', 'x': 'х', 'y': 'й', 'z': 'з',
    }
    result = ""
    for char in word:
        result += latin_to_cyrillic.get(char, char)
    result = re.sub(r'[^а-яёғқўҳ]', '', result)
    return result


def extract_words(text):
    """Matndan alohida so'zlarni ajratib olish"""
    if not text:
        return []
    words = re.split(r'[\s,.\-!?;:\(\)\[\]\"\'\/\\]+', text)
    return [w for w in words if len(w) > 0]


def contains_bad_word(text):
    """Matnda yomon so'z bormi?"""
    if not text:
        return False

    words = extract_words(text)
    normalized_words = [normalize_word(w) for w in words]
    normalized_bad = [normalize_word(w) for w in BAD_WORDS]

    for bad_word in normalized_bad:
        if not bad_word:
            continue
        if len(bad_word) <= 3:
            for word in normalized_words:
                if word == bad_word:
                    return True
        else:
            for word in normalized_words:
                if word == bad_word:
                    return True
            for word in normalized_words:
                if bad_word in word:
                    return True

    return False


# ═══════════════════════════════════════
# НАРХ ИНДЕКСИ — BARCHA PLATFORMALAR УЧУН
# ═══════════════════════════════════════

PRICE_INDEX_MAP = {
    "буқа": "🐄 Буқа/Сигир",
    "сигир": "🐄 Буқа/Сигир",
    "тана": "🐄 Буқа/Сигир",
    "бузоқ": "🐄 Буқа/Сигир",
    "қўй": "🐑 Қўй",
    "қўчқор": "🐑 Қўй",
    "совлиқ": "🐑 Қўй",
    "қўзи": "🐑 Қўй",
    "эчки": "🐐 Эчки",
    "улоқ": "🐐 Эчки",
    "от": "🐴 От",
    "туя": "🐫 Туя",
    "парранда": "🐓 Парранда",
    "барчаси": "📊 Барчаси",
}


def match_price_index(text):
    """Tugma matnini narx indeksi guruhiga moslash."""
    if not text:
        return text

    import re
    clean = re.sub(
        r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF\u200d\uFE0F]',
        '', text
    ).strip()

    clean_lower = clean.lower()

    for key_word, group_name in PRICE_INDEX_MAP.items():
        if key_word in clean_lower:
            return group_name

    fixed = fix_keyboard_text(clean)
    for key_word, group_name in PRICE_INDEX_MAP.items():
        if key_word in fixed.lower():
            return group_name

    return text


def get_notification_users(animal_type, region, price, district=None):
    """Мос кузатувчиларни топиш — ҳайвон тури, вилоят, туман, нарх бўйича"""
    conn = get_connection()
    cursor = conn.cursor()
    p = get_placeholder()

    if DATABASE_URL:
        cursor.execute(f"""
            SELECT user_id
            FROM notifications
            WHERE animal_type = {p}
              AND region = {p}
              AND min_price <= {p}
              AND max_price >= {p}
              AND is_active = TRUE
              AND (district = 'Барчаси' OR district = {p})
        """, (animal_type, region, price, price, district or 'Барчаси'))
    else:
        cursor.execute(f"""
            SELECT user_id
            FROM notifications
            WHERE animal_type = {p}
              AND region = {p}
              AND min_price <= {p}
              AND max_price >= {p}
              AND is_active = 1
              AND (district = 'Барчаси' OR district = {p})
        """, (animal_type, region, price, price, district or 'Барчаси'))

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_user_notifications(user_id):
    conn = get_connection()
    cur = conn.cursor()
    p = get_placeholder()

    cur.execute(f"""
        SELECT id, animal_type, region, district,
               min_price, max_price
        FROM notifications
        WHERE user_id = {p}
        ORDER BY id DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()
    return rows

def delete_notification(notification_id):

    conn = get_connection()
    cur = conn.cursor()

    p = get_placeholder()

    cur.execute(
        f"""
        DELETE FROM notifications
        WHERE id = {p}
        """,
        (notification_id,)
    )

    conn.commit()
    conn.close()

# ═══════════════════════════════════════
# ЭЪЛОН ТАСДИҚЛАШ ТИЗИМИ
# ═══════════════════════════════════════

def get_pending_ad(ad_id):
    """Тасдиқ кутаётган эълонни олиш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT id, user_id, animal_type, quantity, price,
               description, region, district, mfy, phone, username,
               msg_id, reviewed_by
        FROM ads WHERE id = {p} AND status = {p}
    """, (ad_id, 'pending'))
    row = cursor.fetchone()
    conn.close()
    return row

def approve_ad(ad_id, admin_id):
    """Эълонни тасдиқлаш — status='active', reviewed_by=admin_id"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE ads
        SET status = {p}, reviewed_by = {p}
        WHERE id = {p} AND status = {p}
    """, ('active', admin_id, ad_id, 'pending'))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0  # True = тасдиқланди, False = бошқа админ аввал тасдиқлаган


def reject_ad(ad_id, admin_id, reason=""):
    """Эълонни рад қилиш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE ads
        SET status = {p}, reviewed_by = {p}
        WHERE id = {p} AND status = {p}
    """, ('rejected', admin_id, ad_id, 'pending'))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ═══════════════════════════════════════
# БЛОКЛАШ ТИЗИМИ
# ═══════════════════════════════════════

MAX_REJECTIONS = 4  # Шунча марта рад қилинса блокланади


def is_user_blocked(user_id):
    """Фойдаланувчи блокланганми?"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT is_blocked FROM users WHERE user_id = {p}",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        if DATABASE_URL:
            return row[0] == True
        else:
            return row[0] == 1
    return False


def increment_rejection(user_id):
    """Рад қилиш сонини ошириш. 4 марта бўлса блоклаш."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    # Рад сонини ошириш
    cursor.execute(f"""
        UPDATE users
        SET rejection_count = rejection_count + 1
        WHERE user_id = {p}
    """, (user_id,))

    # Янги қийматни олиш
    cursor.execute(
        f"SELECT rejection_count FROM users WHERE user_id = {p}",
        (user_id,)
    )
    row = cursor.fetchone()
    count = row[0] if row else 0

    # Блоклаш текшириш
    blocked = False
    if count >= MAX_REJECTIONS:
        if DATABASE_URL:
            cursor.execute(f"""
                UPDATE users
                SET is_blocked = TRUE, blocked_at = NOW()
                WHERE user_id = {p}
            """, (user_id,))
        else:
            cursor.execute(f"""
                UPDATE users
                SET is_blocked = 1, blocked_at = datetime('now')
                WHERE user_id = {p}
            """, (user_id,))
        blocked = True

    conn.commit()
    conn.close()
    return count, blocked


def unblock_user(user_id):
    """Фойдаланувчини блокдан чиқариш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"""
            UPDATE users
            SET is_blocked = FALSE, rejection_count = 0,
                blocked_at = NULL
            WHERE user_id = {p}
        """, (user_id,))
    else:
        cursor.execute(f"""
            UPDATE users
            SET is_blocked = 0, rejection_count = 0,
                blocked_at = NULL
            WHERE user_id = {p}
        """, (user_id,))
    conn.commit()
    conn.close()


def get_rejection_count(user_id):
    """Рад қилишлар сонини олиш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT rejection_count FROM users WHERE user_id = {p}",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0


def get_blocked_users():
    """Блокланган фойдаланувчилар рўйхати"""
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("""
            SELECT user_id, full_name, username,
                   rejection_count, blocked_at
            FROM users
            WHERE is_blocked = TRUE
            ORDER BY blocked_at DESC
        """)
    else:
        cursor.execute("""
            SELECT user_id, full_name, username,
                   rejection_count, blocked_at
            FROM users
            WHERE is_blocked = 1
            ORDER BY blocked_at DESC
        """)
    rows = cursor.fetchall()
    conn.close()
    return rows

# Админга юборилган хабарни бошқа Админ томонидан таҳрирлаш (тасдиқлаш ва рад қилиш кнопкаларини)

def save_admin_review_message(ad_id: int, admin_id: int, message_id: int, chat_id: int):
    """Ҳар бир админга юборилган review хабарини базага сақлайди."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if DATABASE_URL:
            cursor.execute(f"""
                INSERT INTO admin_review_messages (ad_id, admin_id, message_id, chat_id)
                VALUES ({p}, {p}, {p}, {p})
                ON CONFLICT (ad_id, admin_id) DO UPDATE
                SET message_id = EXCLUDED.message_id, chat_id = EXCLUDED.chat_id
            """, (ad_id, admin_id, message_id, chat_id))
        else:
            cursor.execute(f"""
                INSERT OR REPLACE INTO admin_review_messages (ad_id, admin_id, message_id, chat_id)
                VALUES ({p}, {p}, {p}, {p})
            """, (ad_id, admin_id, message_id, chat_id))
        conn.commit()
    except Exception as e:
        logging.error(f"save_admin_review_message хато: {e}")
    finally:
        conn.close()
 
 
def get_admin_review_messages(ad_id: int) -> list:
    """ad_id бўйича барча админлар учун (admin_id, message_id, chat_id) қайтаради."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"""
            SELECT admin_id, message_id, chat_id
            FROM admin_review_messages
            WHERE ad_id = {p}
        """, (ad_id,))
        return cursor.fetchall()
    except Exception as e:
        logging.error(f"get_admin_review_messages хато: {e}")
        return []
    finally:
        conn.close()
 
 
def delete_admin_review_messages(ad_id: int):
    """Эълон кўрилгандан кейин базадан тозалаш."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"DELETE FROM admin_review_messages WHERE ad_id = {p}",
            (ad_id,)
        )
        conn.commit()
    except Exception as e:
        logging.error(f"delete_admin_review_messages хато: {e}")
    finally:
        conn.close()

def is_premium_user(user_id: int) -> bool:
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT is_premium FROM users WHERE user_id = {p}",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    return bool(row[0])

# ═══════════════════════════════════════
# ОЙЛИК ЭЪЛОН ЛИМИТИ
# ═══════════════════════════════════════

MAX_ADS_PER_MONTH_REGULAR = 15
MAX_ADS_PER_MONTH_PREMIUM = 150


def get_monthly_ad_count(user_id: int) -> int:
    """
    Жорий ойда фойдаланувчи яратган эълонлар сони.
    Статусидан қатий назар (active, sold, deleted, rejected)
    Барчаси саналади — ўчириш лимитни тикламайди.
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute(f"""
            SELECT COUNT(*) FROM ads
            WHERE user_id = {p}
              AND created_at >= DATE_TRUNC('month', NOW())
        """, (user_id,))
    else:
        cursor.execute(f"""
            SELECT COUNT(*) FROM ads
            WHERE user_id = {p}
              AND created_at >= DATE('now', 'start of month')
        """, (user_id,))

    count = cursor.fetchone()[0]
    conn.close()
    return count
# Телефон рақамини тозалаш
def clean_phone(phone: str) -> str:
    """Телефон рақамдан ортиқча белгиларни тозалаш"""
    if not phone:
        return phone
    import re
    cleaned = re.sub(r'[\s\-\.\,\(\)\[\]\/]', '', phone)
    return cleaned

def get_price_range(animal_type):
    """Ҳайвон тури учун ўртача нарх"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    prices = []

    cursor.execute(f"""
        SELECT price::bigint FROM ads
        WHERE animal_type = {p} AND status = 'active'
          AND price ~ '^\d+$'
    """, (animal_type,))
    for r in cursor.fetchall():
        if r[0] and int(r[0]) > 0:
            prices.append(int(r[0]))

    cursor.execute(f"""
        SELECT price FROM market_prices
        WHERE animal_type = {p}
    """, (animal_type,))
    for r in cursor.fetchall():
        if r[0] and r[0] > 0:
            prices.append(r[0])

    conn.close()

    if not prices:
        return 0

    return sum(prices) // len(prices)


# ═══════════════════════════════════════
# ВЕТЕРИНАРИЯ ХОДИМЛАРИ — ФОЙДАЛАНУВЧИ ТАКЛИФЛАРИ
# ═══════════════════════════════════════

def add_vet_suggestion(user_id, username, action_type, region, district,
                        role_type, fish=None, lavozim=None, tel=None, comment=None):
    """
    Фойдаланувчи таклифини 'pending' статусда базага сақлайди.
    action_type: 'yangi' | 'ozgartirish'
    role_type:   'bolim_boshligi' | 'lab_mudiri'
    Қайтаради: янги ёзувнинг ID си.
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO vet_suggestions
        (user_id, username, action_type, region, district, role_type,
         fish, lavozim, tel, comment, status)
        VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, 'pending')
    """, (user_id, username, action_type, region, district, role_type,
          fish, lavozim, tel, comment))
    conn.commit()

    if DATABASE_URL:
        cursor.execute("SELECT lastval()")
    else:
        cursor.execute("SELECT last_insert_rowid()")
    new_id = cursor.fetchone()[0]
    conn.close()
    return new_id


def get_pending_vet_suggestions(limit=20):
    """Кутилаётган (pending) барча таклифлар рўйхати, эскидан янгигa."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT id, user_id, username, action_type, region, district,
               role_type, fish, lavozim, tel, comment, created_at
        FROM vet_suggestions
        WHERE status = {p}
        ORDER BY id ASC
        LIMIT {p}
    """, ("pending", limit))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_vet_suggestion_by_id(suggestion_id):
    """Битта таклифни ID бўйича олиш."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT id, user_id, username, action_type, region, district,
               role_type, fish, lavozim, tel, comment, status,
               admin_id, admin_comment, created_at
        FROM vet_suggestions
        WHERE id = {p}
    """, (suggestion_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def count_pending_vet_suggestions():
    """Кутилаётган таклифлар сони (админ менюсида кўрсатиш учун)."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM vet_suggestions WHERE status = {p}", ("pending",))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def review_vet_suggestion(suggestion_id, admin_id, approve: bool, admin_comment=None):
    """
    Админ таклифни тасдиқлайди ёки рад этади.
    approve=True  -> status='approved'
    approve=False -> status='rejected'
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    new_status = "approved" if approve else "rejected"

    if DATABASE_URL:
        cursor.execute(f"""
            UPDATE vet_suggestions
            SET status = {p}, admin_id = {p}, admin_comment = {p}, reviewed_at = NOW()
            WHERE id = {p}
        """, (new_status, admin_id, admin_comment, suggestion_id))
    else:
        cursor.execute(f"""
            UPDATE vet_suggestions
            SET status = {p}, admin_id = {p}, admin_comment = {p}, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = {p}
        """, (new_status, admin_id, admin_comment, suggestion_id))

    conn.commit()
    conn.close()


def get_approved_vet_override(region, district, role_type):
    """
    Берилган (вилоят, туман, лавозим тури) учун ОХИРГИ тасдиқланган
    таклифни қайтаради — бу runtime'да vet_contacts_data.py'даги
    статик маълумотдан устун қўйилади.
    Топилмаса None қайтаради.
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT fish, lavozim, tel
        FROM vet_suggestions
        WHERE status = {p} AND region = {p} AND district = {p} AND role_type = {p}
        ORDER BY id DESC
        LIMIT 1
    """, ("approved", region, district, role_type))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    fish, lavozim, tel = row
    return {"fish": fish, "lavozim": lavozim, "tel": tel}


def update_vet_suggestion_fields(suggestion_id, fish=None, lavozim=None, tel=None):
    """
    Админ таклифни тасдиқлашдан олдин таҳрирлаши учун —
    берилган майдонларни янгилайди (None бўлмаган майдонлар).
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    sets = []
    params = []
    if fish is not None:
        sets.append(f"fish = {p}")
        params.append(fish)
    if lavozim is not None:
        sets.append(f"lavozim = {p}")
        params.append(lavozim)
    if tel is not None:
        sets.append(f"tel = {p}")
        params.append(tel)

    if not sets:
        conn.close()
        return

    params.append(suggestion_id)
    cursor.execute(
        f"UPDATE vet_suggestions SET {', '.join(sets)} WHERE id = {p}",
        tuple(params)
    )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════
# ВИЛОЯТ ↔ ГУРУҲ БОҒЛАШ (кўп-кўпга)
# ═══════════════════════════════════════

def _ensure_region_group_tables():
    """region_groups ва ad_group_posts жадвалларини яратади (мавжуд бўлмаса)."""
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS region_groups (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                chat_title TEXT,
                chat_username TEXT,
                region TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                added_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (chat_id, region)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ad_group_posts (
                id SERIAL PRIMARY KEY,
                ad_id INTEGER NOT NULL,
                chat_id BIGINT NOT NULL,
                message_id BIGINT,
                status TEXT DEFAULT 'pending',
                reviewed_by BIGINT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS region_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                chat_title TEXT,
                chat_username TEXT,
                region TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (chat_id, region)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ad_group_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER,
                status TEXT DEFAULT 'pending',
                reviewed_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    conn.close()


# init_db() ишга тушганда бу жадваллар ҳам яратилиши учун:
# init_db() функциясининг ЎЗИГА қўшимча қатор ёзмасдан,
# бу ерда мустақил ишга туширамиз (import пайтида эмас, чақирилганда)
_region_group_tables_ready = False


def _ensure_ready():
    global _region_group_tables_ready
    if not _region_group_tables_ready:
        _ensure_region_group_tables()
        _region_group_tables_ready = True


def add_region_group(chat_id: int, chat_title: str, chat_username: str, region: str):
    """Гуруҳни (chat_id) берилган вилоятга боғлайди. Мавжуд бўлса — такрорламайди."""
    _ensure_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"""
            INSERT INTO region_groups (chat_id, chat_title, chat_username, region, is_active)
            VALUES ({p}, {p}, {p}, {p}, TRUE)
            ON CONFLICT (chat_id, region) DO UPDATE SET
                chat_title = EXCLUDED.chat_title,
                chat_username = EXCLUDED.chat_username,
                is_active = TRUE
        """, (chat_id, chat_title, chat_username, region))
    else:
        cursor.execute(f"""
            INSERT OR IGNORE INTO region_groups (chat_id, chat_title, chat_username, region, is_active)
            VALUES ({p}, {p}, {p}, {p}, 1)
        """, (chat_id, chat_title, chat_username, region))
        cursor.execute(f"""
            UPDATE region_groups SET chat_title = {p}, chat_username = {p}, is_active = 1
            WHERE chat_id = {p} AND region = {p}
        """, (chat_title, chat_username, chat_id, region))
    conn.commit()
    conn.close()


def get_groups_for_region(region: str):
    """Берилган вилоятга боғланган, актив гуруҳлар рўйхати: [(chat_id, chat_title, chat_username), ...]"""
    _ensure_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"""
            SELECT chat_id, chat_title, chat_username FROM region_groups
            WHERE region = {p} AND is_active = TRUE
        """, (region,))
    else:
        cursor.execute(f"""
            SELECT chat_id, chat_title, chat_username FROM region_groups
            WHERE region = {p} AND is_active = 1
        """, (region,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def deactivate_chat(chat_id: int):
    """Бот гуруҳдан чиқарилганда — шу chat_id'нинг барча боғланишларини ноактив қилади."""
    _ensure_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"UPDATE region_groups SET is_active = FALSE WHERE chat_id = {p}", (chat_id,))
    else:
        cursor.execute(f"UPDATE region_groups SET is_active = 0 WHERE chat_id = {p}", (chat_id,))
    conn.commit()
    conn.close()


def create_ad_group_post(ad_id: int, chat_id: int) -> int:
    """Эълон учун гуруҳга юбориладиган ёзувни pending ҳолатда яратади, ID қайтаради."""
    _ensure_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO ad_group_posts (ad_id, chat_id, status)
        VALUES ({p}, {p}, 'pending')
    """, (ad_id, chat_id))
    conn.commit()
    if DATABASE_URL:
        cursor.execute("SELECT lastval()")
    else:
        cursor.execute("SELECT last_insert_rowid()")
    new_id = cursor.fetchone()[0]
    conn.close()
    return new_id


def set_ad_group_post_message(post_id: int, message_id: int):
    """Гуруҳга жойлангандан кейин, хабар ID сини сақлайди."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE ad_group_posts SET message_id = {p} WHERE id = {p}", (message_id, post_id))
    conn.commit()
    conn.close()


def get_ad_group_post(post_id: int):
    """Битта ёзувни қайтаради: (id, ad_id, chat_id, message_id, status, reviewed_by)"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT id, ad_id, chat_id, message_id, status, reviewed_by
        FROM ad_group_posts WHERE id = {p}
    """, (post_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def review_ad_group_post(post_id: int, admin_id: int, approve: bool):
    """Гуруҳ админи томонидан тасдиқлаш/рад этишни сақлайди."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    new_status = "approved" if approve else "rejected"
    cursor.execute(f"""
        UPDATE ad_group_posts SET status = {p}, reviewed_by = {p} WHERE id = {p}
    """, (new_status, admin_id, post_id))
    conn.commit()
    conn.close()


def get_ad_group_links(ad_id: int):
    """
    Берилган эълон учун — тасдиқланган ва PUBLIC (username'ли) гуруҳлардаги
    ҳаволалар рўйхатини қайтаради: ["https://t.me/username/123", ...]
    Приват гуруҳлар (username йўқ) — ҳавола бўлмагани учун рўйхатга кирмайди.
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT DISTINCT gp.message_id, rg.chat_username
        FROM ad_group_posts gp
        JOIN region_groups rg ON gp.chat_id = rg.chat_id
        WHERE gp.ad_id = {p} AND gp.status = {p} AND rg.chat_username IS NOT NULL
    """, (ad_id, "approved"))
    rows = cursor.fetchall()
    conn.close()
    links = []
    for message_id, chat_username in rows:
        if message_id and chat_username:
            links.append(f"https://t.me/{chat_username}/{message_id}")
    return links


# ═══════════════════════════════════════
# ТЕЗКОР БЛОКЛАШ (админ инline тугма орқали)
# ═══════════════════════════════════════

def force_block_user(user_id: int):
    """Фойдаланувчини рад сонидан қатъи назар, ДАРҲОЛ блоклайди."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"""
            UPDATE users SET is_blocked = TRUE, blocked_at = NOW() WHERE user_id = {p}
        """, (user_id,))
    else:
        cursor.execute(f"""
            UPDATE users SET is_blocked = 1, blocked_at = CURRENT_TIMESTAMP WHERE user_id = {p}
        """, (user_id,))
    conn.commit()
    conn.close()


def _ensure_block_log_table():
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS block_log (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                blocked_by BIGINT NOT NULL,
                ad_id INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS block_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                blocked_by INTEGER NOT NULL,
                ad_id INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    conn.close()


_block_log_ready = False


def log_block(user_id: int, blocked_by: int, ad_id: int = None, reason: str = None):
    """Кимнинг кимни блоклаганини сақлайди (гуруҳ админи ўз рўйхатини кўриши учун)."""
    global _block_log_ready
    if not _block_log_ready:
        _ensure_block_log_table()
        _block_log_ready = True
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO block_log (user_id, blocked_by, ad_id, reason)
        VALUES ({p}, {p}, {p}, {p})
    """, (user_id, blocked_by, ad_id, reason))
    conn.commit()
    conn.close()


def get_blocks_by_admin(admin_id: int):
    """Шу админ (ёки гуруҳ модератори) блоклаган фойдаланувчилар рўйхати."""
    global _block_log_ready
    if not _block_log_ready:
        _ensure_block_log_table()
        _block_log_ready = True
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT bl.user_id, bl.ad_id, bl.reason, bl.created_at, u.full_name, u.username
        FROM block_log bl
        LEFT JOIN users u ON bl.user_id = u.user_id
        WHERE bl.blocked_by = {p}
        ORDER BY bl.created_at DESC
    """, (admin_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_all_active_group_chat_ids():
    """
    Барча актив гуруҳларнинг (chat_id, chat_title, chat_username) рўйхати —
    ҳар бир гуруҳ учун унга боғланган вилоятлар рўйхати билан бирга.
    Қайтаради: {chat_id: {"chat_title":..., "chat_username":..., "regions": [...]}}
    """
    _ensure_ready()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("""
            SELECT chat_id, chat_title, chat_username, region
            FROM region_groups WHERE is_active = TRUE
            ORDER BY chat_title
        """)
    else:
        cursor.execute("""
            SELECT chat_id, chat_title, chat_username, region
            FROM region_groups WHERE is_active = 1
            ORDER BY chat_title
        """)
    rows = cursor.fetchall()
    conn.close()

    result = {}
    for chat_id, chat_title, chat_username, region in rows:
        if chat_id not in result:
            result[chat_id] = {
                "chat_title": chat_title,
                "chat_username": chat_username,
                "regions": []
            }
        result[chat_id]["regions"].append(region)
    return result


def get_regions_for_chat(chat_id: int):
    """Берилган гуруҳга (chat_id) ҳозирча боғланган, актив вилоятлар рўйхати."""
    _ensure_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"""
            SELECT region FROM region_groups
            WHERE chat_id = {p} AND is_active = TRUE
        """, (chat_id,))
    else:
        cursor.execute(f"""
            SELECT region FROM region_groups
            WHERE chat_id = {p} AND is_active = 1
        """, (chat_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def remove_region_group(chat_id: int, region: str):
    """Берилган гуруҳ-вилоят боғланишини ўчиради (фақат шу region, қолганлари сақланади)."""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM region_groups WHERE chat_id = {p} AND region = {p}", (chat_id, region))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════
# ГУРУҲ АДМИНЛАРИ — тасдиқлаш ваколати (Telegram admin emas, BIZNING ro'yxat)
# ═══════════════════════════════════════

def _ensure_group_admins_table():
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_admins (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                granted_by BIGINT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (chat_id, user_id)
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                granted_by INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (chat_id, user_id)
            )
        """)
    conn.commit()
    conn.close()


_group_admins_ready = False


def _ensure_group_admins_ready():
    global _group_admins_ready
    if not _group_admins_ready:
        _ensure_group_admins_table()
        _group_admins_ready = True


def add_group_admin(chat_id: int, user_id: int, granted_by: int = None):
    """Берилган гуруҳ учун тасдиқлаш ваколатини беради (ёки қайта фаоллаштиради)."""
    _ensure_group_admins_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"""
            INSERT INTO group_admins (chat_id, user_id, granted_by, is_active)
            VALUES ({p}, {p}, {p}, TRUE)
            ON CONFLICT (chat_id, user_id) DO UPDATE SET
                is_active = TRUE, granted_by = EXCLUDED.granted_by
        """, (chat_id, user_id, granted_by))
    else:
        cursor.execute(f"""
            INSERT OR IGNORE INTO group_admins (chat_id, user_id, granted_by, is_active)
            VALUES ({p}, {p}, {p}, 1)
        """, (chat_id, user_id, granted_by))
        cursor.execute(f"""
            UPDATE group_admins SET is_active = 1, granted_by = {p}
            WHERE chat_id = {p} AND user_id = {p}
        """, (granted_by, chat_id, user_id))
    conn.commit()
    conn.close()


def remove_group_admin(chat_id: int, user_id: int):
    """Гуруҳ учун тасдиқлаш ваколатини олиб қўяди."""
    _ensure_group_admins_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"""
            UPDATE group_admins SET is_active = FALSE
            WHERE chat_id = {p} AND user_id = {p}
        """, (chat_id, user_id))
    else:
        cursor.execute(f"""
            UPDATE group_admins SET is_active = 0
            WHERE chat_id = {p} AND user_id = {p}
        """, (chat_id, user_id))
    conn.commit()
    conn.close()


def get_group_admin_ids(chat_id: int):
    """Берилган гуруҳ учун тасдиqлаш ваколатига эга user_id'лар рўйхати."""
    _ensure_group_admins_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"SELECT user_id FROM group_admins WHERE chat_id = {p} AND is_active = TRUE", (chat_id,))
    else:
        cursor.execute(f"SELECT user_id FROM group_admins WHERE chat_id = {p} AND is_active = 1", (chat_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def is_group_admin(chat_id: int, user_id: int) -> bool:
    """Шу одам, шу гуруҳ учун тасдиqлаш ваколатига эгами?"""
    return user_id in get_group_admin_ids(chat_id)


def get_chats_managed_by(user_id: int):
    """Шу одам тасдиqлаш ваколатига эга бўлган БАРЧА гуруҳлар (chat_id рўйхати)."""
    _ensure_group_admins_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"SELECT chat_id FROM group_admins WHERE user_id = {p} AND is_active = TRUE", (user_id,))
    else:
        cursor.execute(f"SELECT chat_id FROM group_admins WHERE user_id = {p} AND is_active = 1", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_ad_group_message_ids(ad_id: int):
    """
    Берилган эълоннинг ГУРУҲЛАРДАГИ барча хабарлари: [(chat_id, message_id), ...]
    Статусидан қатъи назар (эълон таҳрирланганда/ўчирилганда ҳаммасини тозалаш учун).
    """
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT chat_id, message_id FROM ad_group_posts
        WHERE ad_id = {p} AND message_id IS NOT NULL
    """, (ad_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


# ═══════════════════════════════════════
# REVIEW ADMINS — яxлит (unified) тасдиqлаш ҳавзаси (DB-backed, config.py'dan dinamik)
# ═══════════════════════════════════════

def _ensure_review_admins_table():
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_admins (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                full_name TEXT,
                username TEXT,
                added_by BIGINT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                full_name TEXT,
                username TEXT,
                added_by INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    conn.close()


_review_admins_ready = False


def _ensure_review_admins_ready():
    global _review_admins_ready
    if not _review_admins_ready:
        _ensure_review_admins_table()
        _review_admins_ready = True


def seed_review_admins_from_config(config_admin_ids):
    """
    main.py ишга тушганда БИР МАРТА чақирилади — config.py'даги
    REVIEW_ADMINS рўйхатини DB'га 'boshlang'ich' сифатида қўшади
    (агар аллақачон бор бўлса — такрорламайди).
    """
    _ensure_review_admins_ready()
    for uid in config_admin_ids:
        add_review_admin(uid, full_name=None, username=None, added_by=None)


def add_review_admin(user_id: int, full_name: str = None, username: str = None, added_by: int = None):
    """Одамни яxлит review_admins ҳавзасига қўшади (ёки қайта фаоллаштиради)."""
    _ensure_review_admins_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"""
            INSERT INTO review_admins (user_id, full_name, username, added_by, is_active)
            VALUES ({p}, {p}, {p}, {p}, TRUE)
            ON CONFLICT (user_id) DO UPDATE SET
                is_active = TRUE,
                full_name = COALESCE(EXCLUDED.full_name, review_admins.full_name),
                username = COALESCE(EXCLUDED.username, review_admins.username)
        """, (user_id, full_name, username, added_by))
    else:
        cursor.execute(f"""
            INSERT OR IGNORE INTO review_admins (user_id, full_name, username, added_by, is_active)
            VALUES ({p}, {p}, {p}, {p}, 1)
        """, (user_id, full_name, username, added_by))
        cursor.execute(f"""
            UPDATE review_admins SET is_active = 1 WHERE user_id = {p}
        """, (user_id,))
    conn.commit()
    conn.close()


def remove_review_admin(user_id: int):
    """Одамни яxлит review_admins ҳавзасидан олиб ташлайди."""
    _ensure_review_admins_ready()
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute(f"UPDATE review_admins SET is_active = FALSE WHERE user_id = {p}", (user_id,))
    else:
        cursor.execute(f"UPDATE review_admins SET is_active = 0 WHERE user_id = {p}", (user_id,))
    conn.commit()
    conn.close()


def get_all_review_admin_ids():
    """Барча актив review_admins ID'лари рўйхати."""
    _ensure_review_admins_ready()
    conn = get_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("SELECT user_id FROM review_admins WHERE is_active = TRUE")
    else:
        cursor.execute("SELECT user_id FROM review_admins WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def is_review_admin(user_id: int) -> bool:
    return user_id in get_all_review_admin_ids()
