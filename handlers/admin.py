import asyncio
import html
import logging

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup

from config import bot, ADMINS, CHANNEL_ID
from database import (
    get_full_statistics, fmt_number, get_connection, get_placeholder,
    unblock_user, get_blocked_users, get_rejection_count, is_premium_user,
    parse_price_text
)
from keyboards import (
    main_menu, admin_menu_keyboard, admin_ads_keyboard,
    admin_prices_keyboard, admin_block_keyboard, admin_premium_keyboard,
    standard_step_keyboard
)

router = Router()


# ═══════════════════════════════════════
# ADMIN FSM STATES
# ═══════════════════════════════════════

class AdminStates(StatesGroup):
    menu = State()
    ads_menu = State()
    prices_menu = State()
    block_menu = State()
    premium_menu = State()
    # Нарх қўшиш
    add_price_animal = State()
    add_price_region = State()
    add_price_value = State()
    add_multi_text = State()
    del_price_id = State()
    del_animal_name = State()
    del_region_name = State()
    del_ad_id = State()
    del_user_ads_id = State()
    unblock_id = State()
    premium_give_id = State()
    premium_remove_id = State()
    broadcast_text = State()


# ═══════════════════════════════════════
# КИРИЛЛ ТЕКШИРИШ
# ═══════════════════════════════════════

VALID_ANIMALS = [
    "Буқа", "Сигир", "Тана", "Бузоқ", "Қўй",
    "Қўчқор", "Совлиқ", "Қўзи", "Эчки", "Улоқ",
    "От", "Туя", "Парранда"
]

VALID_REGIONS = [
    "Қашқадарё", "Сурхондарё", "Тошкент", "Фарғона",
    "Андижон", "Наманган", "Самарқанд", "Бухоро",
    "Навоий", "Жиззах", "Сирдарё", "Хоразм",
    "Қорақалпоғистон"
]


def is_latin(text):
    latin_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    return any(c in latin_chars for c in text)


def validate_animal(text):
    if is_latin(text):
        return None
    if text in VALID_ANIMALS:
        return text
    return None


def validate_region(text):
    if is_latin(text):
        return None
    if text in VALID_REGIONS:
        return text
    return None


def is_admin(user_id):
    return user_id in ADMINS


# ═══════════════════════════════════════
# 🔐 АДМИН МЕНЮ
# ═══════════════════════════════════════

@router.message(F.text == "🔐 Админ панел")
async def admin_panel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Сизга рухсат йўқ.")
        return
    await state.set_state(AdminStates.menu)
    await message.answer(
        "🔐 *Админ панел*\n\n"
        "Бўлимни танланг:",
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard()
    )


# ═══════════════════════════════════════
# 📋 ЭЪЛОНЛАР МЕНЮСИ
# ═══════════════════════════════════════

@router.message(AdminStates.menu, F.text == "📋 Эълонлар")
async def admin_ads_menu(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.ads_menu)
    await message.answer(
        "📋 *Эълонлар бошқариши*\n\n"
        "Керакли амални танланг:",
        parse_mode="Markdown",
        reply_markup=admin_ads_keyboard()
    )


@router.message(AdminStates.ads_menu, F.text == "👁 Эълонларни кўриш")
async def admin_view_ads(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT id, animal_type, quantity, price,
               region, district, status, user_id
        FROM ads ORDER BY id DESC LIMIT 50
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("❌ Базада эълонлар йўқ.")
        return

    status_emoji = {"active": "✅", "sold": "🤝", "deleted": "🗑", "pending": "⏳"}

    text = f"📋 *Эълонлар ({len(rows)} та):*\n\n"
    for ad_id, a_type, qty, price, region, dist, status, uid in rows:
        emoji = status_emoji.get(status, "❓")
        text += (
            f"{emoji} `#{ad_id}` — 🐾 *{a_type}* | "
            f"🔢 {qty} | 💰 {price}\n"
            f"   📍 {region}, {dist} | 👤 {uid}\n\n"
        )

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


@router.message(AdminStates.ads_menu, F.text == "🗑 ID бўйича ўчириш")
async def ask_del_ad(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.del_ad_id)
    await message.answer(
        "📋 Эълон ID сини киритинг:\n\n"
        "_Кўриш учун: Эълонларни кўриш_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.del_ad_id)
async def do_del_ad(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.ads_menu)
        await message.answer("📋 Эълонлар бошқариши", reply_markup=admin_ads_keyboard())
        return

    try:
        ad_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ ID рақам бўлиши керак!")
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, animal_type, quantity, price, region, district, msg_id FROM ads WHERE id = {p}",
        (ad_id,)
    )
    row = cursor.fetchone()

    if not row:
        await message.answer(f"❌ ID={ad_id} топилмади.")
        conn.close()
        return

    _, a_type, qty, price, region, dist, msg_ids_str = row

    msg_ids = [int(mid) for mid in str(msg_ids_str).split(",") if mid.strip().isdigit()]
    deleted_count = 0
    for msg_id in msg_ids:
        try:
            await bot.delete_message(chat_id=CHANNEL_ID, message_id=msg_id)
            deleted_count += 1
        except Exception as e:
            logging.error(f"Каналдан ўчириш хато: msg_id={msg_id}, error={e}")

    cursor.execute("DELETE FROM ads WHERE id = {p}", (ad_id,))
    conn.commit()
    conn.close()

    await message.answer(
        f"🗑 *Ўчирилди!*\n\n"
        f"🆔 ID: {ad_id}\n"
        f"🐾 {a_type}\n"
        f"💰 {price}\n"
        f"📍 {region}, {dist}\n"
        f"📨 Каналдан: {deleted_count} та хабар ўчирилди",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.ads_menu)
    await message.answer("📋 Давом этинг:", reply_markup=admin_ads_keyboard())


@router.message(AdminStates.ads_menu, F.text == "🗑 Фойдаланувчи эълонларини ўчириш")
async def ask_del_user_ads(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.del_user_ads_id)
    await message.answer(
        "📋 Фойдаланувчи USER_ID сини киритинг:",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.del_user_ads_id)
async def do_del_user_ads(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.ads_menu)
        await message.answer("📋 Эълонлар бошқариши", reply_markup=admin_ads_keyboard())
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ USER_ID рақам бўлиши керак!")
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM ads WHERE user_id = {p}", (user_id,))
    count = cursor.fetchone()[0]

    if count == 0:
        await message.answer(f"❌ USER_ID={user_id} учун эълонлар топилмади.")
        conn.close()
        return

    cursor.execute("SELECT msg_id FROM ads WHERE user_id = {p}", (user_id,))
    all_msg_ids = cursor.fetchall()

    deleted_count = 0
    for (msg_ids_str,) in all_msg_ids:
        msg_ids = [int(mid) for mid in str(msg_ids_str).split(",") if mid.strip().isdigit()]
        for msg_id in msg_ids:
            try:
                await bot.delete_message(chat_id=CHANNEL_ID, message_id=msg_id)
                deleted_count += 1
            except Exception:
                pass

    cursor.execute("DELETE FROM ads WHERE user_id = {p}", (user_id,))
    conn.commit()
    conn.close()

    await message.answer(
        f"🗑 USER_ID={user_id} — *{count} та* эълон ўчирилди.\n"
        f"📨 Каналдан: {deleted_count} та хабар ўчирилди.",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.ads_menu)
    await message.answer("📋 Давом этинг:", reply_markup=admin_ads_keyboard())


# ═══════════════════════════════════════
# 💰 НАРХЛАР МЕНЮСИ
# ═══════════════════════════════════════

@router.message(AdminStates.menu, F.text == "💰 Нархлар")
async def admin_prices_menu(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.prices_menu)
    await message.answer(
        "💰 *Нархлар бошқариши*\n\n"
        "Керакли амални танланг:",
        parse_mode="Markdown",
        reply_markup=admin_prices_keyboard()
    )


# ── Нарх қўшиш (3 қадам) ──

@router.message(AdminStates.prices_menu, F.text == "➕ Нарх қўшиш")
async def ask_add_price(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.add_price_animal)
    await message.answer(
        "🐾 Ҳайвон турини киритинг (кириллда):\n"
        f"Рўхат: {', '.join(VALID_ANIMALS)}",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.add_price_animal)
async def add_price_animal(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    animal = validate_animal(message.text.strip())
    if animal is None:
        await message.answer(
            f"⚠️ Нотўғри. Кириллда ёзинг:\n{', '.join(VALID_ANIMALS)}"
        )
        return

    await state.update_data(mp_animal=animal)
    await state.set_state(AdminStates.add_price_region)
    await message.answer(
        "📍 Вилоятни киритинг (кириллда):\n"
        f"Рўхат: {', '.join(VALID_REGIONS)}"
    )


@router.message(AdminStates.add_price_region)
async def add_price_region(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    region = validate_region(message.text.strip())
    if region is None:
        await message.answer(
            f"⚠️ Нотўғри. Кириллда ёзинг:\n{', '.join(VALID_REGIONS)}"
        )
        return

    await state.update_data(mp_region=region)
    await state.set_state(AdminStates.add_price_value)
    await message.answer(
        "💰 Нархни киритинг (сўмда):\nМасалан: `15000000`",
        parse_mode="Markdown"
    )


@router.message(AdminStates.add_price_value)
async def add_price_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    try:
        price = int(message.text.strip().replace(" ", ""))
    except ValueError:
        await message.answer("⚠️ Нарх рақам бўлиши керак!")
        return

    if price < 1000:
        await message.answer("⚠️ Нарх жуда кичик!")
        return

    data = await state.get_data()
    animal = data.get("mp_animal")
    region = data.get("mp_region")

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO market_prices (user_id, animal_type, region, price)
        VALUES ({p}, {p}, {p}, {p})
    """, (message.from_user.id, animal, region, price))
    conn.commit()
    conn.close()

    await message.answer(
        f"✅ *Нарх киритилди!*\n\n"
        f"🐾 {animal}\n"
        f"📍 {region}\n"
        f"💰 {price:,} сўм",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.prices_menu)
    await message.answer("💰 Давом этинг:", reply_markup=admin_prices_keyboard())


# ── Кўп нарх қўшиш ──

@router.message(AdminStates.prices_menu, F.text == "➕ Кўп нарх қўшиш")
async def ask_add_multi(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.add_multi_text)
    await message.answer(
        "📋 *Формат:*\n\n"
        "Ҳар сатрда битта:\n"
        "`Сигир Тошкент 15000000`\n"
        "`Қўй Самарқанд 3500000`\n"
        "`Эчки Фарғона 2800000`\n\n"
        "⚠️ Фақат кириллда!",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.add_multi_text)
async def do_add_multi(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    lines = message.text.strip().split("\n")
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    success = 0
    errors = []

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 3:
            errors.append(f"❌ `{line.strip()}` — format xato")
            continue

        animal = validate_animal(parts[0])
        region = validate_region(parts[1])

        if animal is None:
            errors.append(f"❌ `{parts[0]}` — ҳайвон нотўғри")
            continue
        if region is None:
            errors.append(f"❌ `{parts[1]}` — вилоят нотўғри")
            continue

        try:
            price = int(parts[2].replace(" ", ""))
        except ValueError:
            errors.append(f"❌ `{line.strip()}` — нарх хато")
            continue

        if price < 1000:
            errors.append(f"❌ `{line.strip()}` — нарх кичик")
            continue

        cursor.execute(f"""
            INSERT INTO market_prices (user_id, animal_type, region, price)
            VALUES ({p}, {p}, {p}, {p})
        """, (message.from_user.id, animal, region, price))
        success += 1

    conn.commit()
    conn.close()

    text = f"✅ *{success} та нарх киритилди!*\n"
    if errors:
        text += f"\n❌ *Хатолар ({len(errors)}):*\n"
        text += "\n".join(errors[:10])

    await message.answer(text, parse_mode="Markdown")
    await state.set_state(AdminStates.prices_menu)
    await message.answer("💰 Давом этинг:", reply_markup=admin_prices_keyboard())


# ── Нархларни кўриш ──

@router.message(AdminStates.prices_menu, F.text == "👁 Нархларни кўриш")
async def admin_view_prices(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT id, animal_type, region, price, created_at
        FROM market_prices ORDER BY created_at DESC LIMIT 100
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("❌ Базада нархлар йўқ.")
        return

    text = f"📊 *Базадаги нархлар ({len(rows)} та):*\n\n"
    for row_id, animal, region, price, date in rows:
        text += f"🆔 `{row_id}` — 🐾 *{animal}* | 📍 {region} | 💰 {price:,} сўм\n"

    if len(text) > 4000:
        parts = text.split("\n")
        current = ""
        for part in parts:
            if len(current) + len(part) > 3800:
                await message.answer(current, parse_mode="Markdown")
                current = part + "\n"
            else:
                current += part + "\n"
        if current:
            await message.answer(current, parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")


# ── Нархни ID бўйича ўчириш ──

@router.message(AdminStates.prices_menu, F.text == "🗑 Нархни ўчириш ID")
async def ask_del_price(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.del_price_id)
    await message.answer("📋 Нарх ID сини киритинг:", reply_markup=standard_step_keyboard())


@router.message(AdminStates.del_price_id)
async def do_del_price(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    try:
        price_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ ID рақам бўлиши керак!")
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, animal_type, region, price FROM market_prices WHERE id = {p}", (price_id,))
    row = cursor.fetchone()

    if not row:
        await message.answer(f"❌ ID={price_id} топилмади.")
        conn.close()
        return

    _, animal, region, price = row
    cursor.execute("DELETE FROM market_prices WHERE id = {p}", (price_id,))
    conn.commit()
    conn.close()

    await message.answer(
        f"🗑 *Ўчирилди!*\n\n🆔 ID: {price_id}\n🐾 {animal}\n📍 {region}\n💰 {price:,} сўм",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.prices_menu)
    await message.answer("💰 Давом этинг:", reply_markup=admin_prices_keyboard())


# ── Ҳайвон бўйича ўчириш ──

@router.message(AdminStates.prices_menu, F.text == "🗑 Ҳайвон бўйича ўчириш")
async def ask_del_animal(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.del_animal_name)
    await message.answer(
        f"🐾 Ҳайвон турини киритинг:\nРўхат: {', '.join(VALID_ANIMALS)}",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.del_animal_name)
async def do_del_animal(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    animal = validate_animal(message.text.strip())
    if animal is None:
        await message.answer(f"⚠️ Нотўғри: {message.text}")
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM market_prices WHERE animal_type = {p}", (animal,))
    count = cursor.fetchone()[0]

    if count == 0:
        await message.answer(f"❌ *{animal}* учун нархлар топилмади.")
        conn.close()
        return

    cursor.execute("DELETE FROM market_prices WHERE animal_type = {p}", (animal,))
    conn.commit()
    conn.close()

    await message.answer(f"🗑 *{animal}* — {count} та нарх ўчирилди.", parse_mode="Markdown")
    await state.set_state(AdminStates.prices_menu)
    await message.answer("💰 Давом этинг:", reply_markup=admin_prices_keyboard())


# ── Вилоят бўйича ўчириш ──

@router.message(AdminStates.prices_menu, F.text == "🗑 Вилоят бўйича ўчириш")
async def ask_del_region(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.del_region_name)
    await message.answer(
        f"📍 Вилоятни киритинг:\nРўхат: {', '.join(VALID_REGIONS)}",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.del_region_name)
async def do_del_region(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    region = validate_region(message.text.strip())
    if region is None:
        await message.answer(f"⚠️ Нотўғри: {message.text}")
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM market_prices WHERE region = {p}", (region,))
    count = cursor.fetchone()[0]

    if count == 0:
        await message.answer(f"❌ *{region}* учун нархлар топилмади.")
        conn.close()
        return

    cursor.execute("DELETE FROM market_prices WHERE region = {p}", (region,))
    conn.commit()
    conn.close()

    await message.answer(f"🗑 *{region}* — {count} та нарх ўчирилди.", parse_mode="Markdown")
    await state.set_state(AdminStates.prices_menu)
    await message.answer("💰 Давом этинг:", reply_markup=admin_prices_keyboard())


# ── Барчасини ўчириш ──

@router.message(AdminStates.prices_menu, F.text == "🗑 Барчасини ўчириш")
async def ask_clear_prices(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM market_prices")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        await message.answer("❌ Базада нархлар йўқ.")
        return

    await message.answer(
        f"⚠️ *ДИҚҚАТ!*\n\n"
        f"Базада *{count} та* нарх маълумоти бор.\n"
        f"Буларнинг *БАРЧАСИ* ўчирилади!\n\n"
        f"Тасдиқлаш учун: /clearprices_confirm",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════
# 🚫 БЛОК МЕНЮСИ
# ═══════════════════════════════════════

@router.message(AdminStates.menu, F.text == "🚫 Блок")
async def admin_block_menu(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.block_menu)
    await message.answer(
        "🚫 *Блок бошқариши*",
        parse_mode="Markdown",
        reply_markup=admin_block_keyboard()
    )


@router.message(AdminStates.block_menu, F.text == "🚫 Блокланганлар рўйхати")
async def show_blocked(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    blocked = get_blocked_users()
    if not blocked:
        await message.answer("✅ Блокланган фойдаланувчилар йўқ.")
        return

    text = f"🚫 *Блокланганлар ({len(blocked)} та):*\n\n"
    for user_id, full_name, username, count, blocked_at in blocked:
        uname = f"@{username}" if username else "—"
        text += (
            f"👤 {full_name or '—'} ({uname})\n"
            f"   ID: `{user_id}` | Рад: {count} марта\n\n"
        )

    await message.answer(text, parse_mode="Markdown")


@router.message(AdminStates.block_menu, F.text == "🔓 Блокдан чиқариш")
async def ask_unblock(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.unblock_id)
    await message.answer("📋 USER_ID киритинг:", reply_markup=standard_step_keyboard())


@router.message(AdminStates.unblock_id)
async def do_unblock(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.block_menu)
        await message.answer("🚫 Блок бошқариши", reply_markup=admin_block_keyboard())
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ USER_ID рақам бўлиши керак!")
        return

    unblock_user(user_id)
    await message.answer(f"✅ `{user_id}` блокдан чиқарилди.", parse_mode="Markdown")

    try:
        await bot.send_message(
            chat_id=user_id,
            text="✅ *Блок олинди!*\nЭнди қайтадан эълон бера оласиз.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await state.set_state(AdminStates.block_menu)
    await message.answer("🚫 Давом этинг:", reply_markup=admin_block_keyboard())


# ═══════════════════════════════════════
# 💎 ПРЕМИУМ МЕНЮСИ
# ═══════════════════════════════════════

@router.message(AdminStates.menu, F.text == "💎 Премиум")
async def admin_premium_menu(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.premium_menu)
    await message.answer(
        "💎 *Премиум бошқариши*",
        parse_mode="Markdown",
        reply_markup=admin_premium_keyboard()
    )


@router.message(AdminStates.premium_menu, F.text == "💎 Премиум бериш")
async def ask_premium_give(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.premium_give_id)
    await message.answer("📋 USER_ID киритинг:", reply_markup=standard_step_keyboard())


@router.message(AdminStates.premium_give_id)
async def do_premium_give(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.premium_menu)
        await message.answer("💎 Премиум бошқариши", reply_markup=admin_premium_keyboard())
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ USER_ID рақам бўлиши керак!")
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT full_name, username, is_premium FROM users WHERE user_id = {p}", (user_id,))
    row = cursor.fetchone()

    if not row:
        await message.answer(f"❌ USER_ID={user_id} базада топилмади.")
        conn.close()
        return

    full_name, username, already_premium = row
    if already_premium:
        conn.close()
        await message.answer(f"ℹ️ `{user_id}` аллақачон Премиум.", parse_mode="Markdown")
        return

    if __import__('os').getenv("DATABASE_URL"):
        cursor.execute(f"UPDATE users SET is_premium = TRUE WHERE user_id = {p}", (user_id,))
    else:
        cursor.execute(f"UPDATE users SET is_premium = 1 WHERE user_id = {p}", (user_id,))
    conn.commit()
    conn.close()

    uname = f"@{username}" if username else "—"
    await message.answer(
        f"💎 *Премиум берилди!*\n\n👤 {full_name or '—'} ({uname})\n🆔 `{user_id}`",
        parse_mode="Markdown"
    )

    try:
        await bot.send_message(
            chat_id=user_id,
            text="💎 *Табриклаймиз!*\n\nСизга *Премиум* аъзолик берилди!",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await state.set_state(AdminStates.premium_menu)
    await message.answer("💎 Давом этинг:", reply_markup=admin_premium_keyboard())


@router.message(AdminStates.premium_menu, F.text == "❌ Премиум олиш")
async def ask_premium_remove(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.premium_remove_id)
    await message.answer("📋 USER_ID киритинг:", reply_markup=standard_step_keyboard())


@router.message(AdminStates.premium_remove_id)
async def do_premium_remove(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.premium_menu)
        await message.answer("💎 Премиум бошқариши", reply_markup=admin_premium_keyboard())
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ USER_ID рақам бўлиши керак!")
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if __import__('os').getenv("DATABASE_URL"):
        cursor.execute(f"UPDATE users SET is_premium = FALSE WHERE user_id = {p}", (user_id,))
    else:
        cursor.execute(f"UPDATE users SET is_premium = 0 WHERE user_id = {p}", (user_id,))
    conn.commit()
    conn.close()

    await message.answer(f"✅ `{user_id}` дан Премиум олиб ташланди.", parse_mode="Markdown")
    await state.set_state(AdminStates.premium_menu)
    await message.answer("💎 Давом этинг:", reply_markup=admin_premium_keyboard())


@router.message(AdminStates.premium_menu, F.text == "💎 Премиум рўйхати")
async def show_premium_list(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if __import__('os').getenv("DATABASE_URL"):
        cursor.execute("SELECT user_id, full_name, username FROM users WHERE is_premium = TRUE ORDER BY user_id")
    else:
        cursor.execute("SELECT user_id, full_name, username FROM users WHERE is_premium = 1 ORDER BY user_id")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("💎 Ҳозирча Премиум аъзолар йўқ.")
        return

    text = f"💎 *Премиум аъзолар ({len(rows)} та):*\n\n"
    for uid, full_name, username in rows:
        uname = f"@{username}" if username else "—"
        text += f"👤 {full_name or '—'} ({uname}) — `{uid}`\n"

    await message.answer(text, parse_mode="Markdown")


# ═══════════════════════════════════════
# 📢 ТАРҚАТИШ
# ═══════════════════════════════════════

@router.message(AdminStates.menu, F.text == "📢 Тарқатиш")
async def ask_broadcast(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.broadcast_text)
    await message.answer(
        "📢 Юбориладиган матнни ёзинг:",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.broadcast_text)
async def do_broadcast(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.menu)
        await message.answer("🔐 Админ панел", reply_markup=admin_menu_keyboard())
        return

    broadcast_text = message.text.strip()
    if not broadcast_text:
        await message.answer("⚠️ Матн бўш.")
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    if not users:
        await message.answer("Базада фойдаланувчилар йўқ.")
        return

    sent_count = 0
    failed_count = 0

    status_msg = await message.answer(f"⏳ Юборилмоқда... ({len(users)} та)")

    for user in users:
        uid = user[0]
        try:
            await bot.send_message(chat_id=uid, text=broadcast_text)
            sent_count += 1
        except Exception:
            try:
                await bot.send_message(chat_id=uid, text=html.escape(broadcast_text))
                sent_count += 1
            except Exception:
                failed_count += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"📢 *Тарқатиш якунланди!*\n\n"
        f"✅ Муваффақиятли: {sent_count}\n"
        f"❌ Юборилмади: {failed_count}",
        parse_mode="Markdown"
    )

    await state.set_state(AdminStates.menu)
    await message.answer("🔐 Давом этинг:", reply_markup=admin_menu_keyboard())


# ═══════════════════════════════════════
# 📊 СТАТИСТИКА
# ═══════════════════════════════════════

@router.message(AdminStates.menu, F.text == "📊 Статистика")
async def admin_stats(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    stats = get_full_statistics()

    text = "📈 *БОТ СТАТИСТИКАСИ*\n"
    text += f"{'═' * 28}\n\n"
    text += f"📋 Жами эълонлар: *{stats['total_ads']}* та\n"
    text += f"✅ Фаол: *{stats['active_ads']}* та\n"
    text += f"🤝 Сотилган: *{stats['sold_ads']}* та\n"
    text += f"👥 Фойдаланувчилар: *{stats['total_users']}* та\n"
    text += f"📊 Нарх маълумотлари: *{stats['market_price_entries']}* та\n\n"

    if stats["by_animal"]:
        text += f"🐾 *ҲАЙВОН ТУРЛАРИ БЎЙИЧА:*\n"
        total_active = stats["active_ads"] or 1
        for a_type, count in stats["by_animal"]:
            pct = (count / total_active) * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            text += f"  {a_type}: {count} ({pct:.0f}%)\n  {bar}\n"
        text += "\n"

    if stats["by_region"]:
        text += f"📍 *ВИЛОЯТЛАР БЎЙИЧА:*\n"
        for region, count in stats["by_region"][:7]:
            text += f"  {region}: {count} та\n"
        text += "\n"

    if stats["avg_prices"]:
        text += f"💰 *ЎРТАЧА НАРХЛАР:*\n"
        emoji_map = {
            "Буқа": "🐂", "Сигир": "🐄", "Тана": "🐮", "Бузоқ": "🐮",
            "Қўчқор": "🐏", "Совлиқ": "🐑", "Қўзи": "🐑",
            "Эчки": "🐐", "От": "🐴", "Туя": "🐫", "Парранда": "🐓"
        }
        sorted_prices = sorted(stats["avg_prices"].items(), key=lambda x: x[1]["avg"], reverse=True)
        for a_type, pdata in sorted_prices:
            emoji = emoji_map.get(a_type, "🐾")
            text += (
                f"  {emoji} {a_type}\n"
                f"     Ўртача: {fmt_number(pdata['avg'])} сўм\n"
                f"     ({pdata['count']} та эълон)\n"
            )

    await message.answer(text, parse_mode="Markdown")


# ═══════════════════════════════════════
# 🔍 НАРХ ТЕКШИРИШ
# ═══════════════════════════════════════

@router.message(AdminStates.menu, F.text == "🔍 Нарх текшириш")
async def check_prices(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, animal_type, region, price FROM ads WHERE status = 'active'")
    ads = cursor.fetchall()
    zero_ads = [f"🆔{r[0]} | {r[1]} | {r[2]} | `{r[3]}`" for r in ads if parse_price_text(str(r[3])) == 0]

    cursor.execute("SELECT id, animal_type, region, price FROM market_prices")
    mp = cursor.fetchall()
    zero_mp = [f"🆔{r[0]} | {r[1]} | {r[2]} | `{r[3]}`" for r in mp if r[3] is None or r[3] == 0]

    conn.close()

    text = f"🔍 *Нарх текшириш*\n\n"
    text += f"📋 Ads: {len(ads)} та | Market_prices: {len(mp)} та\n\n"

    if zero_ads:
        text += f"❌ *Ads — нархсиз ({len(zero_ads)} та):*\n"
        for line in zero_ads[:20]:
            text += f"  {line}\n"
    else:
        text += "✅ Ads — барчасида нарх бор\n"

    if zero_mp:
        text += f"\n❌ *Market_prices — нархсиз ({len(zero_mp)} та):*\n"
        for line in zero_mp[:20]:
            text += f"  {line}\n"
    else:
        text += "\n✅ Market_prices — барчасида нарх бор\n"

    await message.answer(text, parse_mode="Markdown")


# ═══════════════════════════════════════
# ОРҚАГА / БОШ МЕНЮ
# ═══════════════════════════════════════

@router.message(AdminStates.menu, F.text == "🏠 Бош меню")
@router.message(AdminStates.ads_menu, F.text == "🔙 Орқага")
@router.message(AdminStates.prices_menu, F.text == "🔙 Орқага")
@router.message(AdminStates.block_menu, F.text == "🔙 Орқага")
@router.message(AdminStates.premium_menu, F.text == "🔙 Орқага")
async def admin_back_to_menu(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🏠 Бош меню", reply_markup=main_menu())
