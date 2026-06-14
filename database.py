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
                status TEXT DEFAULT 'active'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY
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
                status TEXT DEFAULT 'active'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
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

    conn.commit()
    conn.close()
    logging.info(
        "Baza yaratildi (PostgreSQL)" if DATABASE_URL
        else "Baza yaratildi (SQLite)"
    )


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
        'млн', 'миллиoн', 'миллион', 'милион',
        'млион', 'милон', 'million', 'milion', 'mln'
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

    cleaned = ''.join(c for c in text if c.isdigit())
    return int(cleaned) if cleaned else 0


def fmt_number(n):
    """Рақамни форматда кўрсатиш: 15 000 000"""
    return f"{n:,.0f}".replace(",", " ")


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
        # ═══ PostgreSQL ═══
        cursor.execute("""
            SELECT animal_type, region,
                   AVG(price) as avg_price,
                   MIN(price) as min_price,
                   MAX(price) as max_price,
                   COUNT(*) as cnt
            FROM market_prices
            WHERE created_at > NOW() - INTERVAL '30 days'
            GROUP BY animal_type, region
            ORDER BY animal_type, avg_price
        """)
    else:
        # ═══ SQLite ═══
        cursor.execute("""
            SELECT animal_type, region,
                   AVG(price) as avg_price,
                   MIN(price) as min_price,
                   MAX(price) as max_price,
                   COUNT(*) as cnt
            FROM market_prices
            WHERE created_at > datetime('now', '-30 days')
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


def search_ads_db(animal_type=None, region=None, max_price=None, limit=10):
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

def search_all(animal_type=None, region=None):
    """3 манбадан қидириш"""
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    result = {"ads": [], "market_prices": [], "stats": {}}

    # ═══ Эълонлар ═══
    query_ads = f"""
        SELECT id, animal_type, region, price,
               district, description, quantity, user_id
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
    query_ads += " ORDER BY id DESC LIMIT 50"
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
        query_mp += f" AND region = {p}"       # ← ТЎҒИРИЛДИ!
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
