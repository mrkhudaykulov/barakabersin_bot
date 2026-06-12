import asyncio
import logging
import sqlite3
import os  # 👈 Тизим созламаларини ўқиш учун қўшилди
import re
import html

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, \
    InputMediaPhoto, InputMediaVideo
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# ----------- ЭСКИ ИМПОРТЛАР ТАГИДАН ҚЎШИНГ -----------
from calculators import qoy_hisobla, qm_hisobla_sut, qm_hisobla_gosht, fmt

# ----------- СОЗЛАМАЛАР -----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = -1001419724490  # Канал ID си (minus белгиси билан бўлиши шарт)
ADMINS = [72185847, 2134695872]  # Ўз Telegram ID ингиз


logging.basicConfig(level=logging.INFO)

# 🌟 PythonAnywhere текин тарифи учун расмий прокси созламаси:
# from aiogram.client.session.aiohttp import AiohttpSession

# PROXY_URL = "http://proxy.server:3128"
# session = AiohttpSession(proxy=PROXY_URL)

# Ботни прокси сессияси билан ишга туширамиз:
#bot = Bot(token=BOT_TOKEN, session=session)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ----------- БАЗА БИЛАН ИШЛАШ -----------
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
  
    # 🆕 ЯНГИ: Фойдаланувчиларни сақлаш учун жадвал
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)
        
    # 🆕 Нархлар индекси учун алоҳида жадвал
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


# init_db()


# ══════════════════════════════════════════
# 🆕 YORDAMCHI FUNKSIYALAR
# ══════════════════════════════════════════

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

    # Вилоятлар бўйича гуруҳлаш
    stats = {}
    for a_type, region, price_text in rows:
        price = parse_price_text(price_text)
        if price == 0:
            continue

        key = (a_type, region)
        if key not in stats:
            stats[key] = {"prices": [], "count": 0}
        stats[key]["prices"].append(price)
        stats[key]["count"] += 1

    # Натийжаларни ҳисоблаш
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

    # Ҳар бир ҳайвон тури бўйича нарх бўйича саралаш
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

    # Агар max_price берилган бўлса — филтрлаш
    if max_price:
        filtered = []
        for row in rows:
            price = parse_price_text(row[3])
            if price > 0 and price <= max_price:
                filtered.append(row)
        return filtered

    return rows


def search_all(animal_type=None, region=None):
    """
    3 ta manbadan qidiradi:
    1. E'lonlar (ads jadvali)
    2. Bozor narxlari (market_prices jadvali)
    3. Umumiy statistika
    """
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    result = {
        "ads": [],
        "market_prices": [],
        "stats": {}
    }

    # ═══ MANBA 1: E'LONLAR ═══
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

    # ═══ MANBA 2: BOZOR NARXLARI ═══
    query_mp = """
        SELECT animal_type, region, price, created_at
        FROM market_prices
        WHERE 1=1
    """
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

    # ═══ MANBA 3: STATISTIKA ═══
    all_prices = []

    for ad in result["ads"]:
        price = parse_price_text(ad[2])
        if price > 0:
            all_prices.append(price)

    for mp in result["market_prices"]:
        if mp[2] > 0:
            all_prices.append(mp[2])

    if all_prices:
        result["stats"] = {
            "count": len(all_prices),
            "avg": sum(all_prices) / len(all_prices),
            "min": min(all_prices),
            "max": max(all_prices)
        }

    conn.close()
    return result

def get_full_statistics():
    """Тўлиқ статистика"""
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    stats = {}

    # Жами эълонлар
    cursor.execute("SELECT COUNT(*) FROM ads")
    stats["total_ads"] = cursor.fetchone()[0]

    # Фаол эълонлар
    cursor.execute("SELECT COUNT(*) FROM ads WHERE status='active'")
    stats["active_ads"] = cursor.fetchone()[0]

    # Сотилган
    cursor.execute("SELECT COUNT(*) FROM ads WHERE status='sold'")
    stats["sold_ads"] = cursor.fetchone()[0]

    # Жами фойдаланувчилар
    cursor.execute("SELECT COUNT(*) FROM users")
    stats["total_users"] = cursor.fetchone()[0]

    # Ҳайвон турлари бўйича
    cursor.execute("""
        SELECT animal_type, COUNT(*) as cnt
        FROM ads
        WHERE status='active'
        GROUP BY animal_type
        ORDER BY cnt DESC
    """)
    stats["by_animal"] = cursor.fetchall()

    # Вилоятлар бўйича
    cursor.execute("""
        SELECT region, COUNT(*) as cnt
        FROM ads
        WHERE status='active'
        GROUP BY region
        ORDER BY cnt DESC
    """)
    stats["by_region"] = cursor.fetchall()

    # Ўртача нархлар (ҳайвон тури бўйича)
    cursor.execute("""
        SELECT animal_type, price
        FROM ads
        WHERE status='active'
    """)
    raw_prices = cursor.fetchall()

    price_by_animal = {}
    for a_type, price_text in raw_prices:
        price = parse_price_text(price_text)
        if price > 0:
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

    # Бозор нархлари (market_prices)
    cursor.execute("SELECT COUNT(*) FROM market_prices")
    stats["market_price_entries"] = cursor.fetchone()[0]

    conn.close()
    return stats



# ----------- FSM (ҲОЛАТЛАР) -----------
class AdStates(StatesGroup):
    photo = State()
    animal_type = State()
    region = State()
    district = State()
    mfy = State()
    quantity = State()
    price = State()
    description = State()
    phone = State()

# Янги Калькулятор FSM ҳолатлари
class CalcStates(StatesGroup):
    menu = State()
    # Қўй босқичлари
    qoy_bosh = State()
    qoy_narx = State()
    qoy_qozi_narx = State()
    qoy_em_narx = State()
    # Қорамол босқичлари
    qm_bosh = State()
    qm_yon = State()
    qm_sut_vazn = State()
    qm_narx = State()
    qm_em_narx = State()

# 🆕 Қидириш учун ҳолатлар
class SearchStates(StatesGroup):
    animal_type = State()
    region = State()
    # max_price = State()

# 🆕 Нарх киритиш учун ҳолатлар
class PriceInputStates(StatesGroup):
    animal_type = State()
    region = State()
    price = State()



# ----------- КЛАВИАТУРАЛАР -----------
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Эълон бериш"), KeyboardButton(text="🔍 Эълон қидириш")],
        [KeyboardButton(text="📊 Нархлар индекси"), KeyboardButton(text="📈 Статистика")],
        [KeyboardButton(text="💰 Нарх киритиш"), KeyboardButton(text="🧮 Ферма калькулятори")],
        [KeyboardButton(text="🗂 Менинг эълонларим"), KeyboardButton(text="🏠 Бош меню")]
    ], resize_keyboard=True)



# 🆕 Калькулятор учун янги клавиатуралар (Исталган жойига қўшинг)
def calc_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🐑 Қўй калькулятори"), KeyboardButton(text="🐄 Қорамол калькулятори")],
        [KeyboardButton(text="🏠 Бош меню")]
    ], resize_keyboard=True)

def calc_qoramol_direction_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🥛 Сут"), KeyboardButton(text="🥩 Гўшт")],
        [KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="❌ Бекор қилиш")]
    ], resize_keyboard=True)

def step_navigation():
    return [KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="❌ Бекор қилиш")]


def cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Бекор қилиш")]], resize_keyboard=True)


def photo_confirm_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📥 Расмларни тасдиқлаш")],
        step_navigation()
    ], resize_keyboard=True)

'''
def animal_types_keyboard():
    keyboard = [[KeyboardButton(text=t)] for t in ["Буқа", "Қўй", "От", "Эчки", "Парранда", "Бошқа"]]
    keyboard.append(step_navigation())
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
'''
def animal_types_keyboard():
    builder = ReplyKeyboardBuilder()

    # Ҳайвон турлари рўйхати
    types_list = ["Буқа", "Сигир", "Тана", "Бузоқ", "Қўчқор", "Совлиқ", "Қўзи", "Эчки", "Улоқ", "От", "Туя", "Парранда", "Бошқа"]

    # 1. Ҳайвонларни кетма-кет қўшамиз
    for t in types_list:
        builder.add(KeyboardButton(text=t))

    # Ҳайвонларни 2 тадан ёнма-ён қилиб терамиз
    builder.adjust(2)

    # 2. Пастки навигация тугмаларини алоҳида янги қаторга чиройли қилиб қўшамиз
    builder.row(KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="❌ Бекор қилиш"))

    return builder.as_markup(resize_keyboard=True)

'''
def regions_keyboard():
    regions = ["Тошкент", "Фарғона", "Андижон", "Наманган", "Самарқанд", "Бухоро", "Қашқадарё", "Сурхондарё", "Хоразм",
               "Навоий", "Жиззах", "Сирдарё", "Қорақалпоғистон"]
    keyboard = [[KeyboardButton(text=r)] for r in regions]
    keyboard.append(step_navigation())
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
'''

def regions_keyboard():
    builder = ReplyKeyboardBuilder()

    regions = [
        "Қашқадарё", "Сурхондарё", "Тошкент", "Фарғона", "Андижон", "Наманган", "Самарқанд", "Бухоро",
        "Навоий", "Жиззах", "Сирдарё", "Хоразм", "Қорақалпоғистон"
    ]

    # 1. Вилоятларни қурувчига қўшамиз
    for r in regions:
        builder.add(KeyboardButton(text=r))

    # Вилоятларни 2 тадан ёнма-ён жойлаштирамиз
    builder.adjust(2)

    # 2. Навигация тугмаларини энг пастги қаторга ёнма-ён қўшамиз
    builder.row(KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="❌ Бекор қилиш"))

    return builder.as_markup(resize_keyboard=True)

'''
def districts_keyboard(region):
    districts = {
        "Фарғона": ["Олтиариқ", "Марғилон", "Қўқон", "Риштон"],
        "Тошкент": ["Юнусобод", "Чилонзор", "Мирзо Улуғбек", "Қибрай"],
        "Қашқадарё": ["Ғузор", "Қамаши", "Қарши", "Чироқчи", "Кўкдала", "Яккабоғ", "Шаҳрисабз", "Муборак"]
    }
    list_d = districts.get(region, ["Марказ тумани", "Чет тумани"])
    keyboard = [[KeyboardButton(text=d)] for d in list_d]
    keyboard.append(step_navigation())
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
'''

def districts_keyboard(region):
    builder = ReplyKeyboardBuilder()

    districts = {
        "Фарғона": [
            "Бешариқ", "Боғдод", "Бувайда", "Данғара", "Ёзёвон", "Қува",
            "Қувасой", "Қўқон", "Қўштепа", "Марғилон", "Олтиариқ", "Риштон",
            "Сўх", "Тошлоқ", "Ўзбекистон", "Учкўприк", "Фарғона", "Фурқат"
        ],
        "Тошкент": [
            "Пойтахт", "Ангрен", "Бекобод", "Бўка", "Бўстонлиқ", "Зангиота",
            "Қибрай", "Қуйичирчиқ", "Оққўрғон", "Олмалиқ", "Оҳангарон", "Паркент",
            "Пискент", "Тошкент.т", "Ўртачирчиқ", "Чиноз", "Чирчиқ", "Юқоричирчиқ", "Ягийўл", "Нурафшон"
        ],
        "Қашқадарё": [
            "Ғузор", "Деҳқонобод", "Касби", "Китоб", "Косон",
            "Қамаши", "Қарши", "Миришкор", "Чироқчи", "Нишон",
            "Кўкдала", "Яккабоғ", "Шаҳрисабз", "Муборак"
        ],
        "Наманган": [
            "Косонсой", "Мингбулоқ", "Наманган", "Норин", "Поп",
            "Тўрақўрғон", "Уйчи", "Учқўрғон", "Чортоқ", 
            "Чуст", "Янгиқўрғон", "Давлатобод"
        ],
        "Андижон": [
            "Андижон", "Асака", "Балиқчи", "Бўстон", "Булоқбоши",
            "Жалақудуқ", "Избоскан", "Қўрғонтепа", "Марҳамат", 
            "Олтинкўл", "Пахтобод", "Улуғнор", "Хонобод", "Хўжаобод", "Шаҳрихон"
        ],
        "Бухоро": [
            "Бухоро", "Вобкент", "Ғиждувон", "Жондор", "Когон",
            "Қоровулбозор", "Қоракўл", "Олот", "Пешку", "Ромитан", "Шофиркон"
        ],
        "Жиззах": [
            "Арнасой", "Бахмал", "Ғаллаорол", "Дўстлик", "Жиззах",
            "Зарбдор", "Зафаробод", "Зомин", "Мирзачўл", 
            "Пахтакор", "Фориш", "Ш.Рашидов", "Янгиобод"
        ],
        "Қорақалпоғистон": [
            "Амударё", "Беруний", "Бўзатов", "Кегейли", "Қонликўл",
            "Қораўзак", "Қўнғирот", "Мўйноқ", "Нукус", "Тахиатош",
            "Тахтакўпир", "Тўрткўл", "Хўжайли", "Чимбой", "Шуманай", "Элликқала"
        ],
        "Навоий": [
            "Зарафшон", "Кармана", "Конимех", "Қизилтепа",
            "Навбаҳор", "Навоий", "Нурота", "Томди",
            "Учқудуқ", "Хатирчи", "Ғазғон"
        ],
        "Самарқанд": [
            "Булунғур", "Жомбой", "Иштихон", "Каттақўрғон",
            "Қўшработ", "Нарпай", "Нуробод", "Оқдарё", "Пахтачи",
            "Пайариқ", "Пасдарғом", "Самарқанд", "Тойлоқ", "Ургут"
        ],
        "Сирдарё": [
            "Боёвут", "Гулистон", "Мирзаобод", "Оқолтин", "Сайхунобод", 
            "Сардоба", "Сирдарё", "Ховос", "Ширин", "Янгиер"
        ],
        "Сурхондарё": [
            "Ангор", "Бандихон", "Бойсун", "Денов", "Жарқўрғон",
            "Қизириқ", "Қумқўрғон", "Музработ", "Олтинсой", 
            "Сариосиё", "Термиз", "Узун", "Шеробод", "Шўрчи"
        ],
        "Хоразм": [
            "Боғот", "Гурлан", "Қўшкўпир", "Урганч", "Хазорасп",
            "Хива", "Хонқа", "Шовот", "Янгиариқ", "Янгибозор", "Тупроққала"
        ]
    }

    list_d = districts.get(region, ["Марказ тумани", "Чет тумани"])

    # 1. Туманларни цикл орқали қўшамиз
    for d in list_d:
        builder.add(KeyboardButton(text=d))

    # Туманларни 2 тадан қилиб тартиблаймиз
    builder.adjust(2)

    # 2. Навигация тугмаларини пастга жойлаймиз
    builder.row(KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="❌ Бекор қилиш"))

    return builder.as_markup(resize_keyboard=True)


def standard_step_keyboard():
    return ReplyKeyboardMarkup(keyboard=[step_navigation()], resize_keyboard=True)


def description_keyboard():
    keyboard = [
        [KeyboardButton(text="⏭ Ёзмасдан ўтказиб юбориш")],
        step_navigation()
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def phone_keyboard():
    keyboard = [
        [KeyboardButton(text="📱 Рақамни юбориш", request_contact=True)],
        step_navigation()
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    
# 🆕 Нархлар индекси учун клавиатура
def price_index_keyboard():
    builder = ReplyKeyboardBuilder()
    types_list = [
        "🐄 Буқа/Сигир", "🐑 Қўй", "🐐 Эчки",
        "🐴 От", "🐫 Туя", "🐓 Парранда", "📊 Барчаси"
    ]
    for t in types_list:
        builder.add(KeyboardButton(text=t))
    builder.adjust(2)
    builder.row(KeyboardButton(text="🏠 Бош меню"))
    return builder.as_markup(resize_keyboard=True)

# 🆕 Қидириш natijasi учун
def search_animal_keyboard():
    builder = ReplyKeyboardBuilder()
    types_list = [
        "Буқа", "Сигир", "Тана", "Бузоқ",
        "Қўчқор", "Совлиқ", "Қўзи", "Эчки",
        "От", "Туя", "Парранда", "Барчаси"
    ]
    for t in types_list:
        builder.add(KeyboardButton(text=t))
    builder.adjust(2)
    builder.row(KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="❌ Бекор қилиш"))
    return builder.as_markup(resize_keyboard=True)

# 🆕 Вилоят + "Барчаси" вариант билан
def regions_with_all_keyboard():
    builder = ReplyKeyboardBuilder()
    regions = [
        "Барчаси", "Қашқадарё", "Сурхондарё", "Тошкент",
        "Фарғона", "Андижон", "Наманган", "Самарқанд",
        "Бухоро", "Навоий", "Жиззах", "Сирдарё",
        "Хоразм", "Қорақалпоғистон"
    ]
    for r in regions:
        builder.add(KeyboardButton(text=r))
    builder.adjust(2)
    builder.row(KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="❌ Бекор қилиш"))
    return builder.as_markup(resize_keyboard=True)


# ----------- БОТ БУЙРУҚЛАРИ -----------
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    # Фойдаланувчини базага қўшиш (агар аввал кирмаган бўлса)
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        conn.commit()
    except Exception as e:
        logging.error(f"Базага ёзишда хатолик: {e}")
    finally:
        conn.close()

    await message.answer("Ассалому алайкум! Чорва бозор ботига хуш келибсиз.", reply_markup=main_menu())

@dp.message(F.text == "🏠 Бош меню")
async def home_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🏠 Асосий меню",
        reply_markup=main_menu()
    )



# ══════════════════════════════════════════
# 🔐 ADMIN — BOZOR NARXLARINI KIRITISH
# ══════════════════════════════════════════

@dp.message(Command("addprice"))
async def admin_add_price(message: types.Message):
    """Bitta narx kiritish
    Format: /addprice Sigir Toshkent 15000000
    """
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Sizga ruxsat yo'q.")
        return

    parts = message.text.split(maxsplit=3)

    if len(parts) < 4:
        await message.answer(
            "📋 *Format:*\n"
            "`/addprice Hayvon Viloyat Narx`\n\n"
            "*Misol:*\n"
            "`/addprice Sigir Toshkent 15000000`\n"
            "`/addprice Qoy Samarqand 3500000`\n"
            "`/addprice Echki Fargona 2800000`",
            parse_mode="Markdown"
        )
        return

    animal = parts[1]
    region = parts[2]

    try:
        price = int(parts[3].replace(" ", ""))
    except ValueError:
        await message.answer("⚠️ Narx raqam bo'lishi kerak!")
        return

    if price < 1000:
        await message.answer("⚠️ Narx juda kichik!")
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO market_prices
        (user_id, animal_type, region, price)
        VALUES (?, ?, ?, ?)
    """, (message.from_user.id, animal, region, price))
    conn.commit()
    conn.close()

    await message.answer(
        f"✅ *Narx kiritildi!*\n\n"
        f"🐾 {animal}\n"
        f"📍 {region}\n"
        f"💰 {price:,} so'm\n\n"
        f"Ko'rish: /viewprices",
        parse_mode="Markdown"
    )


@dp.message(Command("addmulti"))
async def admin_add_multi(message: types.Message):
    """Ko'p narxni bir vaqtda kiritish

    Format:
    /addmulti
    Sigir Toshkent 15000000
    Qoy Samarqand 3500000
    """
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Sizga ruxsat yo'q.")
        return

    lines = message.text.strip().split("\n")

    if len(lines) < 2:
        await message.answer(
            "📋 *Format:*\n\n"
            "`/addmulti\n"
            "Sigir Toshkent 15000000\n"
            "Qoy Samarqand 3500000\n"
            "Echki Fargona 2800000\n"
            "Buqa Buxoro 20000000`",
            parse_mode="Markdown"
        )
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    success = 0
    errors = []

    for line in lines[1:]:
        parts = line.strip().split()
        if len(parts) < 3:
            errors.append(f"❌ `{line.strip()}` — format xato")
            continue

        animal = parts[0]
        region = parts[1]

        try:
            price = int(parts[2].replace(" ", ""))
        except ValueError:
            errors.append(f"❌ `{line.strip()}` — narx xato")
            continue

        if price < 1000:
            errors.append(f"❌ `{line.strip()}` — narx kichik")
            continue

        cursor.execute("""
            INSERT INTO market_prices
            (user_id, animal_type, region, price)
            VALUES (?, ?, ?, ?)
        """, (message.from_user.id, animal, region, price))
        success += 1

    conn.commit()
    conn.close()

    text = f"✅ *{success} ta narx kiritildi!*\n"
    if errors:
        text += f"\n❌ *Xatolar ({len(errors)}):*\n"
        text += "\n".join(errors[:10])

    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("viewprices"))
async def admin_view_prices(message: types.Message):
    """Bazadagi narxlarni ko'rish"""
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Sizga ruxsat yo'q.")
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT animal_type, region, price, created_at
        FROM market_prices
        ORDER BY created_at DESC
        LIMIT 100
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "❌ Bazada narxlar yo'q.\n\n"
            "Kiritish: /addprice yoki /addmulti"
        )
        return

    # Hayvon turlari bo'yicha guruhlash
    grouped = {}
    for animal, region, price, date in rows:
        if animal not in grouped:
            grouped[animal] = []
        grouped[animal].append((region, price))

    text = f"📊 *Bazadagi narxlar ({len(rows)} ta):*\n\n"

    for animal, items in grouped.items():
        text += f"🐾 *{animal}:*\n"
        # Viloyatlar bo'yicha
        seen = set()
        for region, price in items:
            if region not in seen:
                seen.add(region)
                text += f"   📍 {region}: {price:,} so'm\n"
        text += "\n"

    # Juda uzun bo'lsa — bo'lib yuborish
    if len(text) > 4000:
        parts = text.split("\n\n")
        current = ""
        for part in parts:
            if len(current) + len(part) > 3800:
                await message.answer(current, parse_mode="Markdown")
                current = part + "\n\n"
            else:
                current += part + "\n\n"
        if current:
            await message.answer(current, parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")


@dp.message(Command("clearprices"))
async def admin_clear_prices(message: types.Message):
    """Barcha narxlarni o'chirish"""
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Sizga ruxsat yo'q.")
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM market_prices")
    count = cursor.fetchone()[0]

    if count == 0:
        await message.answer("❌ Bazada narxlar yo'q.")
        conn.close()
        return

    cursor.execute("DELETE FROM market_prices")
    conn.commit()
    conn.close()

    await message.answer(f"🗑 {count} ta narx o'chirildi.")


@dp.message(Command("adminhelp"))
async def admin_help(message: types.Message):
    """Admin buyruqlari ro'yxati"""
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Sizga ruxsat yo'q.")
        return

    await message.answer(
        "🔐 *ADMIN BUYRUQLARI:*\n\n"
        "📝 *Narx kiritish:*\n"
        "`/addprice Sigir Toshkent 15000000`\n"
        "— bitta narx kiritish\n\n"
        "`/addmulti`\n"
        "Sigir Toshkent 15000000\n"
        "Qoy Samarqand 3500000\n"
        "— ko'p narxni bir vaqtda\n\n"
        "👀 *Ko'rish:*\n"
        "`/viewprices` — bazadagi narxlar\n\n"
        "🗑 *O'chirish:*\n"
        "`/clearprices` — barcha narxlarni o'chirish\n\n"
        "📢 *Xabar:*\n"
        "`/broadcast_users matn` — foydalanuvchilarga\n\n"
        "👥 *Statistika:*\n"
        "`/adminhelp` — shu xabar",
        parse_mode="Markdown"
    )





@dp.message(Command("broadcast_users"))
async def broadcast_to_users(message: types.Message):
    
    if message.from_user.id not in ADMINS:
        return

    command_len = len("/broadcast_users")
    broadcast_text = message.text[command_len:].strip()
    
    if not broadcast_text:
        await message.answer("⚠️ Илтимос, буйруқдан кейин тарқатиладиган матнни ҳам ёзинг.\n\nМасалан:\n`/broadcast_users Салом ҳаммага` (формат: HTML)", parse_mode="Markdown")
        return

    # Базадан барча фойдаланувчиларни олиш
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    if not users:
        await message.answer("Базада ҳозирча ҳеч қандай фойдаланувчи йўқ.")
        return

    sent_count = 0
    failed_count = 0

    status_message = await message.answer(f"⏳ Хабар юбориш бошланди (Жами: {len(users)} та фойдаланувчи)...")

    for user in users:
        uid = user[0]
        try:
            # Хабарни фойдаланувчига юбориш
            escaped_text = html.escape(broadcast_text)
            # Агар HTML теглар керак бўлмаса:
            #await bot.send_message(chat_id=uid, text=escaped_text)
            # Ёки парсингни ўчириб қўйиш:
            await bot.send_message(chat_id=uid, text=broadcast_text)  # parse_mode ни олиб ташлаш            
            sent_count += 1
            # Телеграм лимитларига тушиб қолмаслик учун кичик пауза
            await asyncio.sleep(0.05)
        except Exception:
            failed_count += 1

    await status_message.edit_text(
        f"📢 **Тарқатиш якунланди!**\n\n"
        f"✅ Муваффақиятли етказилди: {sent_count} та\n"
        f"❌ Юборилмади (ботдан чиқиб кетганлар): {failed_count} та",
        parse_mode="Markdown"
    )




# ========================================================
# 🧮 ФЕРМА КАЛЬКУЛЯТОРИ АСОСИЙ МЕНЮСИ Ва ХЭНДЛЕРЛАРИ (ЯНГA)
# ========================================================

@dp.message(F.text == "🧮 Ферма калькулятори")
async def calc_main_menu(message: types.Message, state: FSMContext):
    await state.set_state(CalcStates.menu)
    await message.answer("🌾 *Чорвачилик калькулятори* бўлимига хуш келибсиз.\nНимани ҳисобламоқчисиз?", parse_mode="Markdown", reply_markup=calc_menu_keyboard())

# ==============================================================================
# 🎛 МАРКАЗЛАШТИРИЛГАН НАВИГАЦИЯ ТИЗИМИ (❌ БЕКОР ҚИЛИШ ВА 🔙 ОРҚАГА)
# (Бу тизим кодда барча сон/матн кутувчи хэндлерлардан ТЕПАДА туриши шарт!)
# ==============================================================================

@dp.message(F.text == "❌ Бекор қилиш")
async def global_cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ Фаол жараён мавжуд эмас.", reply_markup=main_menu())
        return

    # Агар фойдаланувчи калькулятор бўлимларидан бирида бўлса
    if current_state in [
        CalcStates.menu.state, CalcStates.qoy_bosh.state, CalcStates.qoy_narx.state,
        CalcStates.qoy_qozi_narx.state, CalcStates.qoy_em_narx.state, CalcStates.qm_bosh.state,
        CalcStates.qm_yon.state, CalcStates.qm_sut_vazn.state, CalcStates.qm_narx.state, CalcStates.qm_em_narx.state
    ]:
        await state.set_state(CalcStates.menu)
        await message.answer("🌾 *Чорвачилик калькулятори* бош менюси:", parse_mode="Markdown", reply_markup=calc_menu_keyboard())
        return

    # 🆕 Қидириш ва нарх киритиш учун
    if current_state and current_state.startswith("SearchStates"):
        await state.clear()
        await message.answer("❌ Қидириш бекор қилинди.", reply_markup=main_menu())
        return

    if current_state and current_state.startswith("PriceInputStates"):
        await state.clear()
        await message.answer("❌ Нарх киритиш бекор қилинди.", reply_markup=main_menu())
        return

    
    # Агар эълон бериш ёки бошқа жараёнда бўлса
    await state.clear()
    await message.answer("❌ Жараён бекор қилинди.", reply_markup=main_menu())


@dp.message(F.text == "🔙 Орқага")
async def global_back_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ Фаол жараён мавжуд эмас.", reply_markup=main_menu())
        return

    # ═══ Қидириш учун орқага ═══
    if current_state == SearchStates.animal_type.state:
        await state.clear()
        await message.answer("🏠 Асосий меню", reply_markup=main_menu())
        return

    elif current_state == SearchStates.region.state:
        await state.set_state(SearchStates.animal_type)
        await message.answer("🔙 Ҳайвон турини қайта танланг:", reply_markup=search_animal_keyboard())
        return

    # ═══ Нарх киритиш учун орқага ═══
    elif current_state == PriceInputStates.animal_type.state:
        await state.clear()
        await message.answer("🏠 Асосий меню", reply_markup=main_menu())
        return

    elif current_state == PriceInputStates.region.state:
        await state.set_state(PriceInputStates.animal_type)
        await message.answer("🔙 Ҳайвон турини қайта танланг:", reply_markup=search_animal_keyboard())
        return

    elif current_state == PriceInputStates.price.state:
        await state.set_state(PriceInputStates.region)
        await message.answer("🔙 Вилоятни қайта танланг:", reply_markup=regions_keyboard())
        return


    # ------------------------------------------
    # 🐑 ҚЎЙ КАЛЬКУЛЯТОРИ ОҚИМИ
    # ------------------------------------------
    elif current_state == CalcStates.qoy_bosh.state:
        await state.set_state(CalcStates.menu)
        await message.answer("🌾 *Чорвачилик калькулятори* бўлимига хуш килибсиз.\nНимани ҳисобламоқчисиз?", parse_mode="Markdown", reply_markup=calc_menu_keyboard())
        return

    elif current_state == CalcStates.qoy_narx.state:
        await state.set_state(CalcStates.qoy_bosh)
        await message.answer("1️⃣ *Совлиқ қўйлар сонини* киритинг:\n_(масалан: 20)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())
        return

    elif current_state == CalcStates.qoy_qozi_narx.state:
        await state.set_state(CalcStates.qoy_narx)
        await message.answer("2️⃣ *1 та совлиқ қўй ўртача нархини* киритинг (сўм):\n_(масалан: 3 500 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())
        return

    elif current_state == CalcStates.qoy_em_narx.state:
        await state.set_state(CalcStates.qoy_qozi_narx)
        await message.answer("3️⃣ *1 та қўзининг сотилиш нархини* киритинг (сўм):\n_(масалан: 1 200 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())
        return

    # ------------------------------------------
    # 🐄 ҚОРАМОЛ КАЛЬКУЛЯТОРИ ОҚИМИ
    # ------------------------------------------
    elif current_state == CalcStates.qm_bosh.state:
        await state.set_state(CalcStates.menu)
        await message.answer("🌾 *Чорвачилик калькулятори* бўлимига хуш келибсиз.\nНимани ҳисобламоқчисиз?", parse_mode="Markdown", reply_markup=calc_menu_keyboard())
        return

    elif current_state == CalcStates.qm_yon.state:
        await state.set_state(CalcStates.qm_bosh)
        await message.answer("1️⃣ *Сигирлар (ёки она моллар) сонини* киритинг:\n_(масалан: 10)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())
        return

    elif current_state == CalcStates.qm_sut_vazn.state:
        await state.set_state(CalcStates.qm_yon)
        await message.answer("2️⃣ *Йўналишни танланг:*", reply_markup=calc_qoramol_direction_keyboard())
        return

    elif current_state == CalcStates.qm_narx.state:
        await state.set_state(CalcStates.qm_sut_vazn)
        data = await state.get_data()
        if data.get("qm_yon") == "sut":
            await message.answer("3️⃣ *1 та сигирнинг кунлик сут миқдорини* киритинг (литр):\n_(масалан: 15)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())
        else:
            await message.answer("3️⃣ *1 та молнинг ўртача тирик вазнини* киритинг (кг):\n_(масалан: 400)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())
        return

    elif current_state == CalcStates.qm_em_narx.state:
        await state.set_state(CalcStates.qm_narx)
        data = await state.get_data()
        if data.get("qm_yon") == "sut":
            await message.answer("4️⃣ *1 литр сут сотилиш нархини* киритинг (сўм):\n_(масалан: 4 500)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())
        else:
            await message.answer("4️⃣ *1 кг тирик вазн нархини* киритинг (сўм):\n_(масалан: 25 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())
        return

    # ------------------------------------------
    # 📝 ЭЪЛОН БЕРИШ ЖАРАЁНИ (AdStates) - Имловий хатолар тузатилди
    # ------------------------------------------
    elif current_state == AdStates.animal_type.state:
        await state.set_state(AdStates.photo)
        await message.answer("🔙 Расм юбориш босқичига қайтилди. Расм/видео юборинг ва 'Тасдиқлаш'ни босинг:", reply_markup=photo_confirm_keyboard())
        return

    elif current_state == AdStates.region.state:
        await state.set_state(AdStates.animal_type)
        await message.answer("🔙 Ҳайвон турини қайта танланг:", reply_markup=animal_types_keyboard())
        return

    elif current_state == AdStates.district.state:
        await state.set_state(AdStates.region)
        await message.answer("🔙 Вилоятни қайта танланг:", reply_markup=regions_keyboard())
        return

    elif current_state == AdStates.mfy.state:
        data = await state.get_data()
        await state.set_state(AdStates.district)
        await message.answer("🔙 Туманни қайта танланг:", reply_markup=districts_keyboard(data.get('region')))
        return

    elif current_state == AdStates.quantity.state:
        await state.set_state(AdStates.mfy)
        await message.answer("🔙 МФЙ номини қайта ёзинг:", reply_markup=standard_step_keyboard())
        return

    elif current_state == AdStates.price.state:
        await state.set_state(AdStates.quantity)
        await message.answer("🔙 Сонини қайта киритинг:", reply_markup=standard_step_keyboard())
        return

    elif current_state == AdStates.description.state:
        await state.set_state(AdStates.price)  # 👈 Тузатилди: CalcStates эмас, AdStates бўлди
        await message.answer("🔙 Нархини қайта киритинг:", reply_markup=standard_step_keyboard())
        return

    elif current_state == AdStates.phone.state:
        await state.set_state(AdStates.description)
        await message.answer("🔙 Изоҳ бўлимига қайтилди. Қўшимча изоҳ ёзинг ёки тугмани босинг:", reply_markup=description_keyboard())
        return

# ==============================================================================



# ══════════════════════════════════════════
# 📊 НАРХЛАР ИНДЕКСИ
# ══════════════════════════════════════════
@dp.message(F.text == "📊 Нархлар индекси")
async def price_index_start(message: types.Message, state: FSMContext):
    await state.set_state(CalcStates.menu)  # Бекор қилиш учун
    await message.answer(
        "📊 *Нархлар индекси*\n\n"
        "Эълонлар асосида ўртача нархларни кўрсатади.\n"
        "Қайси ҳайвон турини кўрмоқчисиз?",
        parse_mode="Markdown",
        reply_markup=price_index_keyboard()
    )

@dp.message(F.text.in_(["🐄 Буқа/Сигир", "🐑 Қўй", "🐐 Эчки",
                         "🐴 От", "🐫 Туя", "🐓 Парранда"]))
async def price_index_show(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current is not None and current != CalcStates.menu.state:
        return
    
    animal_map = {
        "🐄 Буқа/Сигир": ["Буқа", "Сигир", "Тана", "Бузоқ"],
        "🐑 Қўй": ["Қўчқор", "Совлиқ", "Қўзи"],
        "🐐 Эчки": ["Эчки", "Улоқ"],
        "🐴 От": ["От"],
        "🐫 Туя": ["Туя"],
        "🐓 Парранда": ["Парранда"]
    }

    animal_types = animal_map.get(message.text, [])
    placeholders = ','.join(['?' for _ in animal_types])

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    # ── E'lonlardan ──
    cursor.execute(f"""
        SELECT animal_type, region, price
        FROM ads
        WHERE status = 'active'
          AND animal_type IN ({placeholders})
    """, animal_types)
    ad_rows = cursor.fetchall()

    # ── ✅ Market prices dan (YANGI QO'SHILDI) ──
    cursor.execute(f"""
        SELECT animal_type, region, price
        FROM market_prices
        WHERE animal_type IN ({placeholders})
    """, animal_types)
    mp_rows = cursor.fetchall()

    conn.close()

    # ── Ikkalasini birlashtirish ──
    region_data = {}

    for a_type, region, price_text in ad_rows:
        price = parse_price_text(price_text)
        if price > 0:
            if region not in region_data:
                region_data[region] = []
            region_data[region].append(price)

    for a_type, region, price in mp_rows:
        if price > 0:
            if region not in region_data:
                region_data[region] = []
            region_data[region].append(price)

    if not region_data:
        await message.answer(
            f"❌ {message.text} учун маълумот йўқ.\n\n"
            f"Биринчи бўлиб эълон беринг ёки нарх киритинг!",
            reply_markup=price_index_keyboard()
        )
        return

    # ── Natijani shakllantirish (oldingi kod davom etadi) ──
    text = f"📊 *{message.text} — нархлар индекси*\n"
    text += f"{'─' * 30}\n\n"

    sorted_regions = sorted(
        region_data.items(),
        key=lambda x: sum(x[1]) / len(x[1])
    )

    total_prices = []

    for region, prices in sorted_regions:
        avg = sum(prices) / len(prices)
        total_prices.extend(prices)
        text += f"📍 *{region}*\n"
        text += f"   Ўртача: {fmt_number(avg)} сўм\n"
        text += f"   Мин: {fmt_number(min(prices))}"
        text += f" | Макс: {fmt_number(max(prices))}\n"
        text += f"   📝 {len(prices)} та\n\n"

    if len(sorted_regions) >= 2:
        cheap = sorted_regions[0]
        exp = sorted_regions[-1]
        cheap_avg = sum(cheap[1]) / len(cheap[1])
        exp_avg = sum(exp[1]) / len(exp[1])

        text += f"{'─' * 30}\n"
        text += f"💰 Энг арзон: *{cheap[0]}*"
        text += f" ({fmt_number(cheap_avg)} сўм)\n"
        text += f"💎 Энг қиммат: *{exp[0]}*"
        text += f" ({fmt_number(exp_avg)} сўм)\n"

        if cheap_avg > 0:
            diff = ((exp_avg / cheap_avg) - 1) * 100
            text += f"📈 Фарқ: *{diff:.0f}%*\n"

    text += f"\n📊 Жами {len(total_prices)} та маълумот"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=price_index_keyboard()
    )




@dp.message(F.text == "📊 Барчаси")
async def price_index_all(message: types.Message):
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    # ── E'lonlardan ──
    cursor.execute("""
        SELECT animal_type, price
        FROM ads
        WHERE status = 'active'
    """)
    ad_rows = cursor.fetchall()

    # ── Market prices dan ──
    cursor.execute("""
        SELECT animal_type, price
        FROM market_prices
    """)
    mp_rows = cursor.fetchall()

    conn.close()

    if not ad_rows and not mp_rows:
        await message.answer(
            "❌ Ҳозирча нарх маълумотлари йўқ.",
            reply_markup=price_index_keyboard()
        )
        return

    animal_data = {}

    # E'lonlardan
    for a_type, price_text in ad_rows:
        price = parse_price_text(price_text)
        if price > 0:
            if a_type not in animal_data:
                animal_data[a_type] = []
            animal_data[a_type].append(price)

    # Market prices dan
    for a_type, price in mp_rows:
        if price > 0:
            if a_type not in animal_data:
                animal_data[a_type] = []
            animal_data[a_type].append(price)

    if not animal_data:
        await message.answer(
            "❌ Маълумот йўқ.",
            reply_markup=price_index_keyboard()
        )
        return

    text = "📊 *БАРЧА ҲАЙВОН ТУРЛАРИ — нархлар индекси*\n"
    text += f"{'─' * 30}\n\n"

    emoji_map = {
        "Буқа": "🐂", "Сигир": "🐄", "Тана": "🐮",
        "Бузоқ": "🐮", "Қўчқор": "🐏", "Совлиқ": "🐑",
        "Қўзи": "🐑", "Эчки": "🐐", "Улоқ": "🐐",
        "От": "🐴", "Туя": "🐫", "Парранда": "🐓"
    }

    sorted_animals = sorted(
        animal_data.items(),
        key=lambda x: sum(x[1]) / len(x[1]),
        reverse=True
    )

    for a_type, prices in sorted_animals:
        emoji = emoji_map.get(a_type, "🐾")
        avg = sum(prices) / len(prices)
        text += f"{emoji} *{a_type}*\n"
        text += f"   Ўртача: {fmt_number(avg)} сўм\n"
        text += f"   Мин: {fmt_number(min(prices))}"
        text += f" | Макс: {fmt_number(max(prices))}\n"
        text += f"   📝 {len(prices)} та\n\n"

    total = sum(len(v) for v in animal_data.values())
    text += f"\n📊 Жами {total} та маълумот"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=price_index_keyboard()
    )




# ══════════════════════════════════════════
# 🔍 ЭЪЛОН ҚИДИРИШ
# ══════════════════════════════════════════

@dp.message(F.text == "🔍 Эълон қидириш")
async def search_start(message: types.Message, state: FSMContext):
    await state.set_state(SearchStates.animal_type)
    await message.answer(
        "🔍 *Эълон қидириш*\n\n"
        "Қайси ҳайвон турини қидирмоқчисиз?",
        parse_mode="Markdown",
        reply_markup=search_animal_keyboard()
    )

@dp.message(SearchStates.animal_type)
async def search_animal(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return  # Глобал хэндлер ишлайди

    search_type = None if message.text == "Барчаси" else message.text
    await state.update_data(search_animal=search_type)
    await state.set_state(SearchStates.region)
    await message.answer(
        "📍 Қайси вилоятни қидирмоқчисиз?",
        reply_markup=regions_with_all_keyboard()
    )

@dp.message(SearchStates.region)
async def search_region(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return

    search_region_val = None if message.text == "Барчаси" else message.text
    data = await state.get_data()
    search_animal = data.get("search_animal")

    # ✅ search_all dan foydalaning
    results = search_all(
        animal_type=search_animal,
        region=search_region_val
    )

    animal_text = search_animal if search_animal else "Барчаси"
    region_text = search_region_val if search_region_val else "Барча вилоятлар"

    text = f"🔍 *Қидириш натийжалари*\n"
    text += f"🐾 {animal_text} | 📍 {region_text}\n"
    text += f"{'─' * 30}\n\n"

    has_data = False

    # ── 1. STATISTIKA ──
    if results["stats"]:
        s = results["stats"]
        text += f"📊 *УМИЙ МАЪЛУМОТ:*\n"
        text += f"   📝 Маълумотлар: *{s['count']}* та\n"
        text += f"   💰 Ўртача: *{fmt_number(s['avg'])}* сўм\n"
        text += f"   ⬇️ Арзон: *{fmt_number(s['min'])}* сўм\n"
        text += f"   ⬆️ Қиммат: *{fmt_number(s['max'])}* сўм\n\n"
        has_data = True

    # ── 2. BOZOR NARXLARI ──
    if results["market_prices"]:
        by_region = {}
        for mp in results["market_prices"]:
            r = mp[1]
            p = mp[2]
            if r not in by_region:
                by_region[r] = []
            by_region[r].append(p)

        text += f"📈 *БОЗОР НАРХЛАРИ:*\n"
        sorted_regions = sorted(
            by_region.items(),
            key=lambda x: sum(x[1]) / len(x[1])
        )
        for region, prices in sorted_regions:
            avg = sum(prices) / len(prices)
            text += f"  📍 *{region}*: {fmt_number(avg)} сўм"
            text += f" ({len(prices)} та)\n"
        text += "\n"
        has_data = True

    # ── 3. E'LONLAR ──
    if results["ads"]:
        text += f"📋 *ЭЪЛОНЛАР ({len(results['ads'])} та):*\n\n"
        for i, ad in enumerate(results["ads"][:5], 1):
            a_type, region, price, district, desc, qty = ad
            text += f"*{i}.* {a_type} — {qty}\n"
            text += f"   💰 {price}\n"
            text += f"   📍 {region}, {district}\n"
            if desc and desc != "Киритилмаган":
                text += f"   📝 {desc}\n"
            text += "\n"
        has_data = True

    # ── 4. HECH NARSA TOPILMASA ──
    if not has_data:
        text += (
            "❌ *Маълумот топилмади.*\n\n"
            "💡 *Тавсия:*\n"
            "• Бошқа ҳайвон турини синаб кўринг\n"
            "• \"Барчаси\" вилоятини танланг\n"
            "• Ўзингиз нарх киритинг"
        )
    elif results["stats"]:
        s = results["stats"]
        text += (
            f"💡 *Маслаҳат:*\n"
            f"Ўртача: {fmt_number(s['avg'] * 0.9)} — "
            f"{fmt_number(s['avg'] * 1.1)} сўм атрофида"
        )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    await state.clear()



# ══════════════════════════════════════════
# 📈 СТАТИСТИКА
# ══════════════════════════════════════════

@dp.message(F.text == "📈 Статистика")
async def show_statistics(message: types.Message):
    stats = get_full_statistics()

    text = "📈 *БОТ СТАТИСТИКАСИ*\n"
    text += f"{'═' * 28}\n\n"

    # Умумий
    text += f"📋 Жами эълонлар: *{stats['total_ads']}* та\n"
    text += f"✅ Фаол: *{stats['active_ads']}* та\n"
    text += f"🤝 Сотилган: *{stats['sold_ads']}* та\n"
    text += f"👥 Фойдаланувчилар: *{stats['total_users']}* та\n"
    text += f"📊 Нарх маълумотлари: *{stats['market_price_entries']}* та\n\n"

    # Ҳайвон турлари бўйича
    if stats["by_animal"]:
        text += f"🐾 *ҲАЙВОН ТУРЛАРИ БЎЙИЧА:*\n"
        total_active = stats["active_ads"] or 1
        for a_type, count in stats["by_animal"]:
            pct = (count / total_active) * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            text += f"  {a_type}: {count} ({pct:.0f}%)\n  {bar}\n"
        text += "\n"

    # Вилоятлар бўйича
    if stats["by_region"]:
        text += f"📍 *ВИЛОЯТЛАР БЎЙИЧА:*\n"
        for region, count in stats["by_region"][:7]:  # Топ 7
            text += f"  {region}: {count} та\n"
        text += "\n"

    # Ўртача нархлар
    if stats["avg_prices"]:
        text += f"💰 *ЎРТАЧА НАРХЛАР:*\n"
        emoji_map = {
            "Буқа": "🐂", "Сигир": "🐄", "Тана": "🐮", "Бузоқ": "🐮",
            "Қўчқор": "🐏", "Совлиқ": "🐑", "Қўзи": "🐑",
            "Эчки": "🐐", "От": "🐴", "Туя": "🐫", "Парранда": "🐓"
        }

        sorted_prices = sorted(
            stats["avg_prices"].items(),
            key=lambda x: x[1]["avg"],
            reverse=True
        )

        for a_type, pdata in sorted_prices:
            emoji = emoji_map.get(a_type, "🐾")
            text += (
                f"  {emoji} {a_type}\n"
                f"     Ўртача: {fmt_number(pdata['avg'])} сўм\n"
                f"     ({pdata['count']} та эълон)\n"
            )

    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu())



# ══════════════════════════════════════════
# ➕ БОЗОР НАРХИНИ КИРИТИШ (CROWDSOURCED)
# ══════════════════════════════════════════
# Бу handler мавjud "➕ Эълон бериш" дан ФАРҚЛИ
# Фақат нарх киритилади, расм/телефон СОРАЛМАЙДИ

# 🆕 Бош менюга қўшимча тугма қўшинг
# (Биринчи қадамдаги main_menu га қўшинг)
# [KeyboardButton(text="💰 Нарх киритиш")]

# ХЭНДЛЕРЛАР:
@dp.message(F.text == "💰 Нарх киритиш")
async def market_price_start(message: types.Message, state: FSMContext):
    await state.set_state(PriceInputStates.animal_type)
    await message.answer(
        "💰 *Бозор нархи киритиш*\n\n"
        "Бу бўлимда сиз бозорда кўрган нархингизни\n"
        "киритишингиз мумкин. Эълон эмас — фақат нарх маълумоти.\n\n"
        "Қайси ҳайвон тури?",
        parse_mode="Markdown",
        reply_markup=search_animal_keyboard()
    )

@dp.message(PriceInputStates.animal_type)
async def market_price_animal(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    await state.update_data(mp_animal=message.text)
    await state.set_state(PriceInputStates.region)
    await message.answer(
        "📍 Қайси вилоятда кўрдингиз?",
        reply_markup=regions_keyboard()
    )

@dp.message(PriceInputStates.region)
async def market_price_region(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return

    await state.update_data(mp_region=message.text)
    await state.set_state(PriceInputStates.price)
    await message.answer(
        "💰 Нархни киритинг (сўмда):\n"
        "_(масалан: 15000000)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )

@dp.message(PriceInputStates.price)
async def market_price_save(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return

    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1000:
        await message.answer("⚠️ Тўғри нарх киритинг (рақамда):")
        return

    price = int(val)
    data = await state.get_data()
    animal = data.get("mp_animal")
    region = data.get("mp_region")

    # Базага сақлаш
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO market_prices (user_id, animal_type, region, price)
        VALUES (?, ?, ?, ?)
    """, (message.from_user.id, animal, region, price))
    conn.commit()
    conn.close()

    await message.answer(
        f"✅ *Нарх сақланди!*\n\n"
        f"🐾 {animal}\n"
        f"📍 {region}\n"
        f"💰 {fmt_number(price)} сўм\n\n"
        f"Рахмат! Сизнинг маълумотингиз бошқаларга ёрдам беради 🙏",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    await state.clear()

    
    



# 🐑 ҚЎЙ КАЛЬКУЛЯТОРИ ОҚИМИ
@dp.message(CalcStates.menu, F.text == "🐑 Қўй калькулятори")
async def qoy_start(message: types.Message, state: FSMContext):
    await state.set_state(CalcStates.qoy_bosh)
    await message.answer("🐑 *Қўй фермаси калькулятори*\n\n1️⃣ *Совлиқ қўйлар сонини* киритинг:\n_(масалан: 20)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qoy_bosh)
async def qoy_bosh_process(message: types.Message, state: FSMContext):
       
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Илтимос, тўғри сон киритинг:")
        return
        
    await state.update_data(qoy_bosh=int(val))
    await state.set_state(CalcStates.qoy_narx)
    await message.answer("2️⃣ *1 та совлиқ қўй ўртача нархини* киритинг (сўм):\n_(масалан: 3 500 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qoy_narx)
async def qoy_narx_process(message: types.Message, state: FSMContext):
        
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 100:
        await message.answer("⚠️ Илтимос, тўғри нарх киритинг:")
        return
        
    await state.update_data(qoy_narx=int(val))
    await state.set_state(CalcStates.qoy_qozi_narx)
    await message.answer("3️⃣ *1 та қўзининг сотилиш нархини* киритинг (сўм):\n_(масалан: 1 200 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qoy_qozi_narx)
async def qoy_qozi_process(message: types.Message, state: FSMContext):

    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 100:
        await message.answer("⚠️ Илтимос, тўғри нарх киритинг:")
        return
        
    await state.update_data(qoy_qozi_narx=int(val))
    await state.set_state(CalcStates.qoy_em_narx)
    await message.answer("4️⃣ *Концентрат ем нархини* киритинг (1 кг, сўм):\n_(масалан: 4 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qoy_em_narx)
async def qoy_em_process(message: types.Message, state: FSMContext):

        
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Илтимос, ем нархини тўғри кўрсатинг:")
        return
    
    data = await state.get_data()
    ona = data.get("qoy_bosh")
    narx = data.get("qoy_narx")
    qozi = data.get("qoy_qozi_narx")
    em = int(val)
    
    try:
        natija = qoy_hisobla(ona, narx, qozi, em)
        await message.answer(natija, parse_mode="Markdown", reply_markup=calc_menu_keyboard())
        await state.set_state(CalcStates.menu)
    except Exception as e:
        logging.error(f"Қўй калькулятори хатоси: {e}")
        await message.answer(f"⚠️ Ҳисоблашда хатолик юз берди:\n{e}")



# 🐄 ҚОРАМОЛ КАЛЬКУЛЯТОРИ ОҚИМИ
@dp.message(CalcStates.menu, F.text == "🐄 Қорамол калькулятори")
async def qoramol_start(message: types.Message, state: FSMContext):
    await state.set_state(CalcStates.qm_bosh)
    await message.answer("🐄 *Қорамол фермаси калькулятори*\n\n1️⃣ *Сигирлар (она моллар) сонини* киритинг:\n_(масалан: 10)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qm_bosh)
async def qm_bosh_process(message: types.Message, state: FSMContext):
        
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Илтимос, сонини тўғри рақамда киритинг:")
        return
        
    await state.update_data(qm_bosh=int(val))
    await state.set_state(CalcStates.qm_yon)
    await message.answer("2️⃣ *Йўналишни танланг:*", reply_markup=calc_qoramol_direction_keyboard())

@dp.message(CalcStates.qm_yon)
async def qm_yon_process(message: types.Message, state: FSMContext):
        
    if message.text not in ["🥛 Сут", "🥩 Гўшт"]:
        await message.answer("⚠️ Илтимос, пастки тугмалардан бирини танланг:")
        return
    
    direction = "sut" if "Сут" in message.text else "gosht"
    await state.update_data(qm_yon=direction)
    await state.set_state(CalcStates.qm_sut_vazn)
    
    if direction == "sut":
        await message.answer("3️⃣ *1 та сигирнинг кунлик сут миқдорини* киритинг (литр):\n_(масалан: 15)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())
    else:
        await message.answer("3️⃣ *1 та молнинг ўртача тирик вазнини* киритинг (кг):\n_(семиртириб сотиш вазни, масалан: 400)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qm_sut_vazn)
async def qm_sut_vazn_process(message: types.Message, state: FSMContext):
    
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ ХАТО. Тўғри қиймат киритинг:")
        return
        
    await state.update_data(qm_sut_vazn=int(val))
    await state.set_state(CalcStates.qm_narx)
    
    data = await state.get_data()
    if data.get("qm_yon") == "sut":
        await message.answer("4️⃣ *1 литр сут сотилиш нархини* киритинг (сўм):\n_(масалан: 4 500)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())
    else:
        await message.answer("4️⃣ *1 кг тирик вазн нархини* киритинг (сўм):\n_(масалан: 25 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qm_narx)
async def qm_narx_process(message: types.Message, state: FSMContext):
    data = await state.get_data()
    direction = data.get("qm_yon")
    
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 100:
        await message.answer("⚠️ Тўғри нарх киритинг:")
        return
        
    await state.update_data(qm_narx=int(val))
    await state.set_state(CalcStates.qm_em_narx)
    await message.answer("5️⃣ *Комбикорм (ем) ўртача нархини* киритинг (1 кг, сўм):\n_(масалан: 5 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qm_em_narx)
async def qm_em_process(message: types.Message, state: FSMContext):
    data = await state.get_data()
    direction = data.get("qm_yon")

    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Тўғри ем нархини киритинг:")
        return
    
    bosh = data.get("qm_bosh")
    sut_vazn = data.get("qm_sut_vazn")
    narx = data.get("qm_narx")
    em = int(val)
    
    try:
        if direction == "sut":
            natija = qm_hisobla_sut(bosh, sut_vazn, narx, em)
        else:
            natija = qm_hisobla_gosht(bosh, sut_vazn, narx, em)
    
        await message.answer(natija, parse_mode="Markdown", reply_markup=calc_menu_keyboard())
        await state.set_state(CalcStates.menu)
    
    except Exception as e:
        logging.error(f"Қорамол калькулятори хатоси: {e}")
        await message.answer(f"⚠️ Ҳисоблашда хатолик юз берди:\n{e}")
    



# ----------- ЭЪЛОН БЕРИШ ЖАРАЁНИ -----------
@dp.message(F.text == "➕ Эълон бериш")
async def start_ad(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(AdStates.photo)
    await state.update_data(media_list=[])
    await message.answer(
        "Илтимос, ҳайвоннинг расмларини ёки видеосини юборинг (Бир нечта юборишингиз мумкин).\n\nЮбориб бўлгач '📥 Расмларни тасдиқлаш' тугмасини босинг:",
        reply_markup=cancel_keyboard())


@dp.message(AdStates.photo, F.photo | F.video)
async def process_photo(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    media_list = user_data.get("media_list", [])
    if message.photo:
        media_list.append({"type": "photo", "file_id": message.photo[-1].file_id})
    elif message.video:
        media_list.append({"type": "video", "file_id": message.video.file_id})
    await state.update_data(media_list=media_list)
    await message.answer(
        f"✅ {len(media_list)}-медиа қабул қилинди. Яна юборишингиз мумкин. Тугатсангиз, пастки тугмани босинг:",
        reply_markup=photo_confirm_keyboard())


@dp.message(AdStates.photo, F.text == "📥 Расмларни тасдиқлаш")
async def confirm_photos(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    media_list = user_data.get("media_list", [])
    if not media_list:
        await message.answer("⚠️ Илтимос, камида 1 та расм юборинг.")
        return
    await state.set_state(AdStates.animal_type)
    await message.answer("Ҳайвон турини танланг:", reply_markup=animal_types_keyboard())


@dp.message(AdStates.photo)
async def process_photo_invalid(message: types.Message, state: FSMContext):
    if message.text == "❌ Бекор қилиш":
        await state.clear()
        await message.answer("❌ Жараён бекор қилинди.", reply_markup=main_menu())
        return
    if message.text == "🔙 Орқага":
        await message.answer("📸 Расм юборинг ёки бекор қилинг.", reply_markup=cancel_keyboard())
        return
    await message.answer("⚠️ Илтимос, фақат расм ёки видео юборинг ва '📥 Расмларни тасдиқлаш' тугмасини босинг.")



@dp.message(AdStates.animal_type)
async def process_type(message: types.Message, state: FSMContext):
    # Навигация тугмаларини текшириш (мустаҳкамлик учун)
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    await state.update_data(animal_type=message.text)
    await state.set_state(AdStates.region)
    await message.answer("Вилоятни танланг:", reply_markup=regions_keyboard())


@dp.message(AdStates.region)
async def process_region(message: types.Message, state: FSMContext):
    # Навигация тугмаларини текшириш (мустаҳкамлик учун)
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    await state.update_data(region=message.text)
    await state.set_state(AdStates.district)
    await message.answer("Туманни танланг:", reply_markup=districts_keyboard(message.text))


@dp.message(AdStates.district)
async def process_district(message: types.Message, state: FSMContext):
    # Навигация тугмаларини текшириш (мустаҳкамлик учун)
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    await state.update_data(district=message.text)
    await state.set_state(AdStates.mfy)
    await message.answer("МФЙ номини ёзинг (матн кўринишида):", reply_markup=standard_step_keyboard())


@dp.message(AdStates.mfy)
async def process_mfy(message: types.Message, state: FSMContext):
    # Навигация тугмаларини текшириш (мустаҳкамлик учун)
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    await state.update_data(mfy=message.text)
    await state.set_state(AdStates.quantity)
    await message.answer("Сонини киритинг (масалан: 2 бош, 5 та):", reply_markup=standard_step_keyboard())


@dp.message(AdStates.quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    # Навигация тугмаларини текшириш (мустаҳкамлик учун)
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    if not any(char.isdigit() for char in message.text):
        await message.answer("⚠️ Илтимос, сонини рақамларда кўрсатинг (масалан: 2 бош ёки 5 та):",
                             reply_markup=standard_step_keyboard())
        return
    await state.update_data(quantity=message.text)
    await state.set_state(AdStates.price)
    await message.answer("Нархини киритинг (масалан: 15 000 000 сўм):", reply_markup=standard_step_keyboard())


@dp.message(AdStates.price)
async def process_price(message: types.Message, state: FSMContext):
    # Навигация тугмаларини текшириш (мустаҳкамлик учун)
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    if not any(char.isdigit() for char in message.text):
        await message.answer("⚠️ Илтимос, нархни рақамларда киритинг (масалан: 12 000 000 сўм):",
                             reply_markup=standard_step_keyboard())
        return
    await state.update_data(price=message.text)
    await state.set_state(AdStates.description)
    await message.answer("Қўшимча изоҳ қолдирасизми? Агар зарур бўлмаса, пастки тугмани босинг:",
                         reply_markup=description_keyboard())


@dp.message(AdStates.description)
async def process_description(message: types.Message, state: FSMContext):
    # Навигация тугмаларини текшириш (мустаҳкамлик учун)
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    if message.text == "⏭ Ёзмасдан ўтказиб юбориш":
        await state.update_data(description="Киритилмаган")
    else:
        await state.update_data(description=message.text)

    await state.set_state(AdStates.phone)
    await message.answer("Алоқа учун телефон рақамингизни юборинг:", reply_markup=phone_keyboard())


@dp.message(AdStates.phone, F.contact | F.text)
async def process_phone(message: types.Message, state: FSMContext):
    if message.text and not any(char.isdigit() for char in message.text):
        await message.answer("⚠️ Илтимос, телефон рақамни тўғри форматда ёзинг.", reply_markup=phone_keyboard())
        return

    phone = message.contact.phone_number if message.contact else message.text
    data = await state.get_data()

    if message.from_user.username:
        username_text = f"@{message.from_user.username}"
    else:
        username_text = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a> (Ник йўқ)"

    caption = (
        f"#️⃣ #{data['animal_type']}\n"
        f"🔢 <b>Сони:</b> {data['quantity']}\n"
        f"💰 <b>Нархи:</b> {data['price']}\n"
        f"📝 <b>Изоҳ:</b> {data['description']}\n"
        f"📍 <b>Манзил:</b> {data['region']} в, {data['district']} т, {data['mfy']} МФЙ\n\n"
        f"📞 <b>Алоқа:</b> {phone}\n"
        f"💬 <b>Телеграм:</b> {username_text}\n\n"
        f"Админсиз эълон жойлаш: @{(await bot.get_me()).username}\nКанал: @internetmolbozor"
    )

    media_list = data.get("media_list", [])

    try:
        telegram_media = []
        for i, media in enumerate(media_list):
            if media["type"] == "photo":
                telegram_media.append(
                    InputMediaPhoto(media=media["file_id"], caption=caption if i == 0 else "", parse_mode="HTML"))
            elif media["type"] == "video":
                telegram_media.append(
                    InputMediaVideo(media=media["file_id"], caption=caption if i == 0 else "", parse_mode="HTML"))

        sent_messages = await bot.send_media_group(chat_id=CHANNEL_ID, media=telegram_media)
        msg_ids_str = ",".join([str(msg.message_id) for msg in sent_messages])

        db_username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"

        conn = sqlite3.connect("chorva.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ads (user_id, msg_id, animal_type, quantity, price, description, region, district, mfy, phone, username)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (message.from_user.id, msg_ids_str, data['animal_type'], data['quantity'], data['price'],
              data['description'], data['region'], data['district'], data['mfy'], phone, db_username))
        conn.commit()
        conn.close()

        await message.answer("🎉 Эълонингиз @internetmolbozor каналига муваффақиятли каналга жойланди!", reply_markup=main_menu())
    except Exception as e:
        await message.answer(f"Хатолик юз берди: {e}", reply_markup=main_menu())

    await state.clear()


# ----------- МЕНИНГ ЭЪЛОНЛАРИМ БЎЛИМИ -----------
@dp.message(F.text == "🗂 Менинг эълонларим")
async def my_ads(message: types.Message):
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, animal_type, price, status FROM ads WHERE user_id = ? AND status = 'active'",
                   (message.from_user.id,))
    ads = cursor.fetchall()
    conn.close()

    if not ads:
        await message.answer("Сизда ҳозирча актив эълонлар йўқ.")
        return

    await message.answer("Сизнинг актив эълонларингиз:")
    for ad in ads:
        ad_id, a_type, price, status = ad
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🤝 Сотилди", callback_data=f"sold_{ad_id}"),
                InlineKeyboardButton(text="❌  Ўчириш", callback_data=f"del_{ad_id}")
            ]
        ])
        await message.answer(f"📦 #{a_type} - {price}", reply_markup=inline_kb)


# ----------- ИНЛАЙН ТУГМАЛАР ИШЛОВЧИСИ (ЭДИ ОДДИЙ ВА АЛЬБОМ ЭЪЛОНЛАР УЧУН ҲИМОЯЛАНДИ) -----------
@dp.callback_query(F.data.startswith("sold_") | F.data.startswith("del_"))
async def handle_ad_action(callback: types.CallbackQuery):
    action, ad_id = callback.data.split("_")

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT msg_id, animal_type, quantity, price, region, district, mfy, phone, username FROM ads WHERE id = ?",
        (int(ad_id),))
    ad = cursor.fetchone()

    if not ad:
        await callback.answer("Эълон топилмади.")
        conn.close()
        return

    msg_ids_str, a_type, qty, price, region, dist, mfy, phone, username = ad

    # 🌟 МАНА ШУ ЖОЙДА ХАТОЛИК ТУЗАТИЛДИ (Мажбурий равишда матнга ўгирилиб, кейин бўлинади):
    msg_ids = [int(mid) for mid in str(msg_ids_str).split(",")]

    if action == "sold":
        cursor.execute("UPDATE ads SET status = 'sold' WHERE id = ?", (ad_id,))
        conn.commit()

        new_caption = (
            f"🔴 <b>СОТИЛДИ!</b> 🔴\n\n"
            f"#️⃣ #{a_type}\n"
            f"🔢 <b>Сони:</b> {qty}\n"
            f"💰 <b>Нархи:</b> {price}\n"
            f"📍 <b>Манзил:</b> {region} в, {dist} т\n"
            f"🤝 Харидорга барака берсин!"
        )
        try:
            await bot.edit_message_caption(chat_id=CHANNEL_ID, message_id=msg_ids[0], caption=new_caption,
                                           parse_mode="HTML")
            await callback.message.edit_text("✅ Каналда 'Сотилди' деб белгиланди.")
        except Exception:
            await callback.answer("Постни таҳрирлаб бўлмади.")

    elif action == "del":
        cursor.execute("UPDATE ads SET status = 'deleted' WHERE id = ?", (ad_id,))
        conn.commit()

        for msg_id in msg_ids:
            try:
                await bot.delete_message(chat_id=CHANNEL_ID, message_id=msg_id)
            except Exception:
                pass
        await callback.message.edit_text("❌ Эълон каналдан бутунлай ўчирилди.")

    conn.close()

# ----------- БОТНИ ИШГА ТУШИРИШ (RENDER УЧУН ВЕБ-СЕРВЕР БИЛАН) -----------
from aiohttp import web

# 🌐 Render ботни ўчириб қўймаслиги учун "тириклик" белгисини берувчи саҳифа
async def handle_render_health_check(request):
    return web.Response(text="Бот муваффақиятли ишламоқда!")

async def main_loop():
    # 1. Маълумотлар базасини ишга тушириш
    init_db()

    # 🚀 Веб-серверни созлаш (Render портини банд қилиб туриш учун)
    app = web.Application()
    app.router.add_get("/", handle_render_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render талаб қиладиган махсус PORT созламаси (Free тарифда автоматик 10000 бўлади)
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[*] Веб-сервер {port}-портда муваффақиятли ишга тушди.")

    # 2. Ботнинг асосий тинглаш (Polling) цикли
    while True:
        try:
            print("[*] Бот Телеграм серверига уланмоқда...")
            
            # Узилиш пайтида йиғилиб қолган эски хабарларни тозалаш
            await bot.delete_webhook(drop_pending_updates=True)

            # Ботни ишга тушириш
            await dp.start_polling(bot)

        except Exception as e:
            print(f"\n[!] Хатолик юз берди: {e}")
            print("[!] 15 сониядан кейин автоматик қайта уриниш бошланади...\n")
            await asyncio.sleep(15)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Бот қўлда тўхтатилди.")
