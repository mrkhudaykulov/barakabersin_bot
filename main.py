import asyncio
import logging
import sqlite3
import os  # 👈 Тизим созламаларини ўқиш учун қўшилди

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
    conn.commit()
    conn.close()


init_db()


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

# ----------- КЛАВИАТУРАЛАР -----------
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Эълон бериш"), KeyboardButton(text="🗂 Менинг эълонларим"), KeyboardButton(text="/start")],
        [KeyboardButton(text="🧮 Ферма калькулятори")] # 👈 Янги қўшилди
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
    types_list = ["Буқа", "Сигир", "Тана", "Бузоқ", "Қўчқор", "Совлиқ", "Қўзи", "Эчки", "Улоқ", "От", "Эчки", "Парранда", "Бошқа"]

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
        "Фарғона": ["Бешариқ", "Боғдод", "Бувайда", "Данғара", "Ёзёвон", "Қува", "Қувасой", "Қўқон", "Қўштепа", "Марғилон", "Олтиариқ", "Риштон", "Сўх", "Тошлоқ", "Ўзбекистон", "Учкўприк", "Фарғона", "Фурқат"],
        "Тошкент": ["Пойтахт", "Ангрен", "Бекобод", "Бўка", "Бўстонлиқ", "Зангиота", "Қибрай", "Қуйичирчиқ", "Оққўрғон", "Олмалиқ", "Оҳангарон", "Паркент", "Пискент", "Тошкент.т", "Ўртачирчиқ", "Чиноз", "Чирчиқ", "Юқоричирчиқ", "Ягийўл", "Нурафшон"],
        "Қашқадарё": ["Ғузор", "Деҳқонобод", "Касби", "Китоб", "Косон", "Қамаши", "Қарши", "Миришкор", "Чироқчи", "Нишон", "Кўкдала", "Яккабоғ", "Шаҳрисабз", "Муборак"],
        "Наманган": ["Косонсой", "Мингбулоқ", "Наманган", "Норин", "Поп", "Тўрақўрғон", "Уйчи", "Учқўрғон", "Чортоқ", "Чуст", "Янгиқўрғон", "Давлатобод"],
        "Андижон": ["Андижон", "Асака", "Балиқчи", "Бўстон", "Булоқбоши", "Жалақудуқ", "Избоскан", "Қўрғонтепа", "Марҳамат", "Олтинкўл", "Пахтобод", "Улуғнор", "Хонобод", "Хўжаобод", "Шаҳрихон"],
        "Бухоро": ["Бухоро", "Вобкент", "Ғиждувон", "Жондор", "Когон", "Қоровулбозор", "Қоракўл", "Олот", "Пешку", "Ромитан", "Шофиркон"],
        "Жиззах": ["Арнасой", "Бахмал", "Ғаллаорол", "Дўстлик", "Жиззах", "Зарбдор", "Зафаробод", "Зомин", "Мирзачўл", "Пахтакор", "Фориш", "Ш.Рашидов", "Янгиобод"],
        "Қорақалпоғистон": ["Амударё", "Беруний", "Бўзатов", "Кегейли", "Қонликўл", "Қораўзак", "Қўнғирот", "Мўйноқ", "Нукус", "Тахиатош", "Тахтакўпир", "Тўрткўл", "Хўжайли", "Чимбой", "Шуманай", "Элликқала"],
        "Навоий": ["Зарафшон", "Кармана", "Конимех", "Қизилтепа", "Навбаҳор", "Навоий", "Нурота", "Томди", "Учқудуқ", "Хатирчи", "Ғазғон"],
        "Самарқанд": ["Булунғур", "Жомбой", "Иштихон", "Каттақўрғон", "Қўшработ", "Нарпай", "Нуробод", "Оқдарё", "Пахтачи", "Пайариқ", "Пасдарғом", "Самарқанд", "Тойлоқ", "Ургут"],
        "Сирдарё": ["Боёвут", "Гулистон", "Мирзаобод", "Оқолтин", "Сайхунобод", "Сардоба", "Сирдарё", "Ховос", "Ширин", "Янгиер"],
        "Сурхондарё": ["Ангор", "Бандихон", "Бойсун", "Денов", "Жарқўрғон", "Қизириқ", "Қумқўрғон", "Музработ", "Олтинсой", "Сариосиё", "Термиз", "Узун", "Шеробод", "Шўрчи"],
        "Хоразм": ["Боғот", "Гурлан", "Қўшкўпир", "Урганч", "Хазорасп", "Хива", "Хонқа", "Шовот", "Янгиариқ", "Янгибозор", "Тупроққала"]
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


# ----------- УМУМИЙ БЕКОР ҚИЛИШ ВА ОРҚАГА ҚАЙТИШ (ХЭНДЛЕРЛАР ТЕПАГА ОЛИНДИ) -----------
@dp.message(F.text == "❌ Бекор қилиш")
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Жараён бекор қилинди.", reply_markup=main_menu())


@dp.message(F.text == "🔙 Орқага")
async def back_action(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    if current_state == AdStates.animal_type.state:
        await state.set_state(AdStates.photo)
        await message.answer("🔙 Расм юбориш босқичига қайтилди. Расм/видео юборинг ва 'Тасдиқлаш'ни босинг:",
                             reply_markup=photo_confirm_keyboard())

    elif current_state == AdStates.region.state:
        await state.set_state(AdStates.animal_type)
        await message.answer("🔙 Ҳайвон турини қайта танланг:", reply_markup=animal_types_keyboard())

    elif current_state == AdStates.district.state:
        await state.set_state(AdStates.region)
        await message.answer("🔙 Вилоятни қайта танланг:", reply_markup=regions_keyboard())

    elif current_state == AdStates.mfy.state:
        data = await state.get_data()
        await state.set_state(AdStates.district)
        await message.answer("🔙 Туманни қайта танланг:", reply_markup=districts_keyboard(data.get('region')))

    elif current_state == AdStates.quantity.state:
        await state.set_state(AdStates.mfy)
        await message.answer("🔙 МФЙ номини қайта ёзинг:", reply_markup=standard_step_keyboard())

    elif current_state == AdStates.price.state:
        await state.set_state(AdStates.quantity)
        await message.answer("🔙 Сонини қайта киритинг:", reply_markup=standard_step_keyboard())

    elif current_state == AdStates.description.state:
        await state.set_state(AdStates.price)
        await message.answer("🔙 Нархини қайта киритинг:", reply_markup=standard_step_keyboard())

    elif current_state == AdStates.phone.state:
        await state.set_state(AdStates.description)
        await message.answer("🔙 Изоҳ бўлимига қайтилди. Қўшимча изоҳ ёзинг ёки тугмани босинг:",
                             reply_markup=description_keyboard())


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

@dp.message(Command("broadcast_users"))
async def broadcast_to_users(message: types.Message):
    # Хавфсизлик учун: фақат сиз (админ) хабар тарқата олишингиз учун текширув
    # (Ўзингизнинг Телеграм ID рақамингизни қўйиб қўйинг, масалан: 1234567)
    ADMIN_ID = message.from_user.id  # Ҳозирча буйруқни берган одамга рухсат беради
    
    # Буйруқдан кейинги матнни ажратиб олиш
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
            await bot.send_message(chat_id=uid, text=broadcast_text, parse_mode="HTML")
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

# 🐑 ҚЎЙ КАЛЬКУЛЯТОРИ ОҚИМИ
@dp.message(CalcStates.menu, F.text == "🐑 Қўй калькулятори")
async def qoy_start(message: types.Message, state: FSMContext):
    await state.set_state(CalcStates.qoy_bosh)
    await message.answer("🐑 *Қўй фермаси калькулятори*\n\n1️⃣ *Она қўйлар сонини* киритинг:\n_(масалан: 20)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qoy_bosh)
async def qoy_bosh_process(message: types.Message, state: FSMContext):
    if message.text == "🔙 Орқага":
        await calc_main_menu(message, state)
        return
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Илтимос, тўғри сон киритинг:")
        return
    await state.update_data(qoy_bosh=int(val))
    await state.set_state(CalcStates.qoy_narx)
    await message.answer("2️⃣ *1 та ona қўй ўртача нархини* киритинг (сўм):\n_(масалан: 3 500 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qoy_narx)
async def qoy_narx_process(message: types.Message, state: FSMContext):
    if message.text == "🔙 Орқага":
        await qoy_start(message, state)
        return
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 100:
        await message.answer("⚠️ Илтимос, тўғри нарх киритинг:")
        return
    await state.update_data(qoy_narx=int(val))
    await state.set_state(CalcStates.qoy_qozi_narx)
    await message.answer("3️⃣ *1 та қўзининг сотилиш нархини* киритинг (сўм):\n_(масалан: 1 200 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qoy_qozi_narx)
async def qoy_qozi_process(message: types.Message, state: FSMContext):
    if message.text == "🔙 Орқага":
        await state.set_state(CalcStates.qoy_bosh)
        data = await state.get_data()
        await message.answer(f"🔙 Сон қайта киритилади.\n1️⃣ Она қўйлар сони: {data.get('qoy_bosh')}\nЯнги сон ёзинг:")
        return
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 100:
        await message.answer("⚠️ Илтимос, тўғри нарх киритинг:")
        return
    await state.update_data(qoy_qozi_narx=int(val))
    await state.set_state(CalcStates.qoy_em_narx)
    await message.answer("4️⃣ *Концентрат ем нархини* киритинг (1 кг, сўм):\n_(масалан: 4 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qoy_em_narx)
async def qoy_em_process(message: types.Message, state: FSMContext):
    if message.text == "🔙 Орқага":
        await state.set_state(CalcStates.qoy_narx)
        await message.answer("🔙 2️⃣ Она қўй нархини қайта киритинг:")
        return
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Илтимос, ем нархини тўғри кўрсатинг:")
        return
    
    data = await state.get_data()
    ona = data.get("qoy_bosh")
    narx = data.get("qoy_narx")
    qozi = data.get("qoy_qozi_narx")
    em = int(val)
    
    natija = qoy_hisobla(ona, narx, qozi, em)
    await message.answer(natija, parse_mode="Markdown", reply_markup=calc_menu_keyboard())
    await state.set_state(CalcStates.menu)

# 🐄 ҚОРАМОЛ КАЛЬКУЛЯТОРИ ОҚИМИ
@dp.message(CalcStates.menu, F.text == "🐄 Қорамол калькулятори")
async def qoramol_start(message: types.Message, state: FSMContext):
    await state.set_state(CalcStates.qm_bosh)
    await message.answer("🐄 *Қорамол фермаси калькулятори*\n\n1️⃣ *Сигирлар (ёки она моллар) сонини* киритинг:\n_(масалан: 10)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qm_bosh)
async def qm_bosh_process(message: types.Message, state: FSMContext):
    if message.text == "🔙 Орқага":
        await calc_main_menu(message, state)
        return
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Илтимос, сонини тўғри рақамда киритинг:")
        return
    await state.update_data(qm_bosh=int(val))
    await state.set_state(CalcStates.qm_yon)
    await message.answer("2️⃣ *Йўналишни танланг:*", reply_markup=calc_qoramol_direction_keyboard())

@dp.message(CalcStates.qm_yon)
async def qm_yon_process(message: types.Message, state: FSMContext):
    if message.text == "🔙 Орқага":
        await qoramol_start(message, state)
        return
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
    if message.text == "🔙 Орқага":
        await state.set_state(CalcStates.qm_bosh)
        await message.answer("🔙 Сонни қайта киритинг:")
        return
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
    if message.text == "🔙 Орқага":
        await state.set_state(CalcStates.qm_yon)
        await message.answer("🔙 Йўналишни қайта танланг:", reply_markup=calc_qoramol_direction_keyboard())
        return
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 100:
        await message.answer("⚠️ Тўғри нарх киритинг:")
        return
    await state.update_data(qm_narx=int(val))
    await state.set_state(CalcStates.qm_em_narx)
    await message.answer("5️⃣ *Комбикорм (ем) ўртача нархини* киритинг (1 кг, сўм):\n_(масалан: 5 000)_", parse_mode="Markdown", reply_markup=standard_step_keyboard())

@dp.message(CalcStates.qm_em_narx)
async def qm_em_process(message: types.Message, state: FSMContext):
    if message.text == "🔙 Орқага":
        await state.set_state(CalcStates.qm_sut_vazn)
        await message.answer("🔙 Миқдорни қайта киритинг:")
        return
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Тўғри ем нархини киритинг:")
        return
    
    data = await state.get_data()
    bosh = data.get("qm_bosh")
    yon = data.get("qm_yon")
    sut_vazn = data.get("qm_sut_vazn")
    narx = data.get("qm_narx")
    em = int(val)
    
    if yon == "sut":
        natija = qm_hisobla_sut(bosh, sut_vazn, narx, em)
    else:
        natija = qm_hisobla_gosht(bosh, sut_vazn, narx, em)
        
    await message.answer(natija, parse_mode="Markdown", reply_markup=calc_menu_keyboard())
    await state.set_state(CalcStates.menu)


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
async def process_photo_invalid(message: types.Message):
    await message.answer("⚠️ Илтимос, фақат расм ёки видео юборинг ва кейин '📥 Расмларни тасдиқлаш' тугмасини босинг.")


@dp.message(AdStates.animal_type)
async def process_type(message: types.Message, state: FSMContext):
    await state.update_data(animal_type=message.text)
    await state.set_state(AdStates.region)
    await message.answer("Вилоятни танланг:", reply_markup=regions_keyboard())


@dp.message(AdStates.region)
async def process_region(message: types.Message, state: FSMContext):
    await state.update_data(region=message.text)
    await state.set_state(AdStates.district)
    await message.answer("Туманни танланг:", reply_markup=districts_keyboard(message.text))


@dp.message(AdStates.district)
async def process_district(message: types.Message, state: FSMContext):
    await state.update_data(district=message.text)
    await state.set_state(AdStates.mfy)
    await message.answer("МФЙ номини ёзинг (матн кўринишида):", reply_markup=standard_step_keyboard())


@dp.message(AdStates.mfy)
async def process_mfy(message: types.Message, state: FSMContext):
    await state.update_data(mfy=message.text)
    await state.set_state(AdStates.quantity)
    await message.answer("Сонини киритинг (масалан: 2 бош, 5 та):", reply_markup=standard_step_keyboard())


@dp.message(AdStates.quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    if not any(char.isdigit() for char in message.text):
        await message.answer("⚠️ Илтимос, сонини рақамларда кўрсатинг (масалан: 2 бош ёки 5 та):",
                             reply_markup=standard_step_keyboard())
        return
    await state.update_data(quantity=message.text)
    await state.set_state(AdStates.price)
    await message.answer("Нархини киритинг (масалан: 15 000 000 сўм):", reply_markup=standard_step_keyboard())


@dp.message(AdStates.price)
async def process_price(message: types.Message, state: FSMContext):
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
        f"Эъон бериш: @{(await bot.get_me()).username}\nКанал: @internetmolbozor"
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
        (ad_id,))
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
