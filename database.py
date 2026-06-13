# ⚠️ Chegara: 50 mln dan oshiq narxlar xato deb hisoblanadi
MAX_PRICE = 50_000_000

import sqlite3


def init_db():
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

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


def parse_price_text(text):
    """Матндаги нархни рақамга айлантириш"""
    cleaned = ''.join(c for c in str(text) if c.isdigit())
    return int(cleaned) if cleaned else 0


def fmt_number(n):
    """Рақамни оддий форматда кўрсатиш: 15 000 000"""
    return f"{n:,.0f}".replace(",", " ")


def get_price_index(animal_type=None):
    """Эълонлар асосида нархлар индексини ҳисоблаш"""
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    query = """
        SELECT animal_type, region, price
        FROM ads
        WHERE status = 'active'
    """
    params = []
    if animal_type:
        query += " AND animal_type = ?"
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
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

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
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    query = """
        SELECT id, animal_type, quantity, price,
               region, district, description
        FROM ads
        WHERE status = 'active'
    """
    params = []

    if animal_type:
        query += " AND animal_type = ?"
        params.append(animal_type)
    if region:
        query += " AND region = ?"
        params.append(region)

    query += " ORDER BY id DESC LIMIT ?"
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


def search_all(animal_type=None, region=None):
    """3 манбадан қидириш: эълонлар, бозор нархлари, статистика"""
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    result = {"ads": [], "market_prices": [], "stats": {}}

    # ═══ Эълонлар ═══
    query_ads = """
        SELECT animal_type, region, price,
               district, description, quantity
        FROM ads
        WHERE status = 'active'
    """
    params_ads = []
    if animal_type:
        query_ads += " AND animal_type = ?"
        params_ads.append(animal_type)
    if region:
        query_ads += " AND region = ?"
        params_ads.append(region)
    query_ads += " ORDER BY id DESC LIMIT 20"
    cursor.execute(query_ads, params_ads)
    result["ads"] = cursor.fetchall()

    # ═══ Бозор нархлари ═══
    query_mp = "SELECT animal_type, region, price, created_at FROM market_prices WHERE 1=1"
    params_mp = []
    if animal_type:
        query_mp += " AND animal_type = ?"
        params_mp.append(animal_type)
    if region:
        query_mp += " AND region = ?"
        params_mp.append(region)
    query_mp += " ORDER BY created_at DESC LIMIT 100"
    cursor.execute(query_mp, params_mp)
    result["market_prices"] = cursor.fetchall()

    conn.close()

    # ═══ Статистика ═══
    all_prices = []
    for ad in result["ads"]:
        price = parse_price_text(ad[2])
        if 0 < price <= MAX_PRICE:
            all_prices.append(price)
    for mp in result["market_prices"]:
        if 0 < mp[2] <= MAX_PRICE:
            all_prices.append(mp[2])

    if all_prices:
        result["stats"] = {
            "count": len(all_prices),
            "avg": sum(all_prices) / len(all_prices),
            "min": min(all_prices),
            "max": max(all_prices)
        }

    return result


def get_full_statistics():
    """Тўлиқ статистика"""
    conn = sqlite3.connect("chorva.db")
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
        if 0 < price <= MAX_PRICE:
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
