import sqlite3

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from database import parse_price_text, fmt_number, get_full_statistics, MAX_PRICE, MIN_PRICE, fix_keyboard_text
from states import CalcStates, PriceInputStates
from keyboards import (
    main_menu, price_index_keyboard, search_animal_keyboard,
    regions_keyboard, standard_step_keyboard
)

router = Router()


# ═══════════════════════════════════════
# 📊 НАРХЛАР ИНДЕКСИ
# ═══════════════════════════════════════

@router.message(F.text == "📊 Нархлар индекси")
async def price_index_start(message: types.Message, state: FSMContext):
    await state.set_state(CalcStates.menu)
    await message.answer(
        "📊 *Нархлар индекси*\n\n"
        "Эълонлар асосида ўртача нархларни кўрсатади.\n"
        "Қайси ҳайвон турини кўрмоқчисиз?",
        parse_mode="Markdown",
        reply_markup=price_index_keyboard()
    )


@router.message(F.text.in_([
    "🐄 Буқа/Сигир", "🐑 Қўй", "🐐 Эчки",
    "🐴 От", "🐫 Туя", "🐓 Парранда"
]))
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
    
    cursor.execute(f"""
        SELECT animal_type, region, price
        FROM ads
        WHERE status = 'active'
          AND animal_type IN ({placeholders})
    """, animal_types)
    ad_rows = cursor.fetchall()

    cursor.execute(f"""
        SELECT animal_type, region, price
        FROM market_prices
        WHERE animal_type IN ({placeholders})
    """, animal_types)
    mp_rows = cursor.fetchall()

    conn.close()

    region_data = {}

    for a_type, region, price_text in ad_rows:
        price = parse_price_text(price_text)
        if MIN_PRICE <= price <= MAX_PRICE:
            if region not in region_data:
                region_data[region] = []
            region_data[region].append(price)

    for a_type, region, price in mp_rows:
        if MIN_PRICE <= price <= MAX_PRICE:
            if region not in region_data:
                region_data[region] = []
            region_data[region].append(price)

    if not region_data:
        await message.answer(
            f"❌ {message.text} учун маълумот йўқ.\n\n"
            f"💰 Нарх киритиш учун \"*💰 Нарх киритиш*\" "
            f"тугмасини босинг.",
            parse_mode="Markdown",
            reply_markup=main_menu()    # ← Асосий менюга қайтади
        )
        return


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


@router.message(F.text == "📊 Барчаси")
async def price_index_all(message: types.Message):
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT animal_type, price
        FROM ads WHERE status = 'active'
    """)
    ad_rows = cursor.fetchall()

    cursor.execute("SELECT animal_type, price FROM market_prices")
    mp_rows = cursor.fetchall()

    conn.close()

    if not ad_rows and not mp_rows:
        await message.answer(
            "❌ Ҳозирча нарх маълумотлари йўқ.",
            reply_markup=price_index_keyboard()
        )
        return

    animal_data = {}

    for a_type, price_text in ad_rows:
        price = parse_price_text(price_text)
        if 0 < price <= MAX_PRICE:
            if a_type not in animal_data:
                animal_data[a_type] = []
            animal_data[a_type].append(price)

    for a_type, price in mp_rows:
        if 0 < price <= MAX_PRICE:
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



# ═══════════════════════════════════════
# 💰 НАРХ КИРИТИШ (CROWDSOURCED)
# ═══════════════════════════════════════

@router.message(F.text == "💰 Нарх киритиш")
async def market_price_start(message: types.Message, state: FSMContext):
    await state.set_state(PriceInputStates.animal_type)
    await message.answer(
        "💰 *Бозор нархи киритиш*\n\n"
        "Бу бўлимда сиз бозорда кўрган нархингизни\n"
        "киритишингиз мумкин. Эълон эмас — фақат нарх маълумоти.\n\n"
        "Қайси ҳайвон тури?",
        parse_mode="Markdown",
        reply_markup=animal_types_keyboard_for_price()
    )


def animal_types_keyboard_for_price():
    """Нарх киритиш учун — Барчаси сиз"""
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    from aiogram.types import KeyboardButton

    builder = ReplyKeyboardBuilder()
    types_list = [
        "Буқа", "Сигир", "Тана", "Бузоқ", "Қўчқор",
        "Совлиқ", "Қўзи", "Эчки", "Улоқ", "От",
        "Туя", "Парранда"
    ]
    for t in types_list:
        builder.add(KeyboardButton(text=t))
    builder.adjust(2)
    builder.row(
        KeyboardButton(text="🔙 Орқага"),
        KeyboardButton(text="❌ Бекор қилиш")
    )
    return builder.as_markup(resize_keyboard=True)


@router.message(PriceInputStates.animal_type)
async def market_price_animal(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    fixed = fix_keyboard_text(message.text)
    await state.update_data(mp_animal=fixed)
    await state.set_state(PriceInputStates.region)
    await message.answer(
        "📍 Қайси вилоятда кўрдингиз?",
        reply_markup=regions_keyboard()
    )


@router.message(PriceInputStates.region)
async def market_price_region(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    fixed = fix_keyboard_text(message.text)
    await state.update_data(mp_region=fixed)
    await state.set_state(PriceInputStates.price)
    await message.answer(
        "💰 Нархни киритинг (сўмда):\n_(масалан: 15000000)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(PriceInputStates.price)
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
        f"Рахмат! Сизнинг маълумотингиз бошқаларга ёрдам беради",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    await state.clear()

