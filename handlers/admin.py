import asyncio
import html
import logging

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, BaseFilter
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
from states import AdminStates

class IsAdmin(BaseFilter):
    """
    Router даражасида қўлланади — шу файлдаги ҲАММА handler'лар учун
    админ эканликни текширади. Янги handler қўшилганда бу текширувни
    алоҳида ёзишни унутиб қўйиш имконсиз (routerнинг ўзи блоклайди).
    """
    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id in ADMINS


router = Router()
router.message.filter(F.chat.type == "private")
router.message.filter(IsAdmin())

# "🔐 Админ панел" тугмасини админ бўлмаган одам босса (ёки матнни қўлда
# ёзса) — юқоридаги router уни блоклайди (handler'га умуман етиб бормайди),
# шунинг учун "рухсат йўқ" хабарини шу алоҳида, ФИЛЬТРСИЗ router беради.
# handlers/__init__.py'да admin.router'дан КЕЙИН рўйхатдан ўтказилиши шарт.
fallback_router = Router()
fallback_router.message.filter(F.chat.type == "private")


@fallback_router.message(F.text == "🔐 Админ панел")
async def admin_panel_denied(message: types.Message):
    await message.answer("⛔ Сизга рухсат йўқ.")




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


# ═══════════════════════════════════════
# 🔐 АДМИН МЕНЮ
# ═══════════════════════════════════════

@router.message(F.text == "🔐 Админ панел")
async def admin_panel(message: types.Message, state: FSMContext):
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
    await state.set_state(AdminStates.ads_menu)
    await message.answer(
        "📋 *Эълонлар бошқариши*\n\n"
        "Керакли амални танланг:",
        parse_mode="Markdown",
        reply_markup=admin_ads_keyboard()
    )


@router.message(AdminStates.ads_menu, F.text == "👁 Эълонларни кўриш")
async def admin_view_ads(message: types.Message, state: FSMContext):
    def _fetch_ads_sync():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, animal_type, quantity, price,
                   region, district, status, user_id
            FROM ads ORDER BY id DESC LIMIT 50
        """)
        result = cursor.fetchall()
        conn.close()
        return result

    rows = await asyncio.to_thread(_fetch_ads_sync)

    if not rows:
        await message.answer("❌ Базада эълонлар йўқ.")
        return

    status_map = {
        "active": "✅",
        "sold": "🤝",
        "deleted": "🗑",
        "pending": "⏳"
    }    

    text = f"📋 *Эълонлар ({len(rows)} та):*\n\n"
    for ad_id, a_type, qty, price, region, dist, status, uid in rows:
        status_emoji = status_map.get(status, "❓")
        text += (
            f"{status_emoji} `#{ad_id}` — *{a_type}* | "
            f" {qty} | 💰 {price}\n"
            f"    {region}, {dist}\n"
            f"   👤 [Фойдаланувчи](tg://user?id={uid}) | "
            f"📌 {status}\n\n"
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
    await state.set_state(AdminStates.del_ad_id)
    await message.answer(
        "📋 Эълон ID сини киритинг:\n\n"
        "_Кўриш учун: Эълонларни кўриш_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.del_ad_id)
async def do_del_ad(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.ads_menu)
        await message.answer("📋 Эълонлар бошқариши", reply_markup=admin_ads_keyboard())
        return

    try:
        ad_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ ID рақам бўлиши керак!")
        return

    def _fetch_ad_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, animal_type, quantity, price, region, district, msg_id FROM ads WHERE id = {p}
            """, (ad_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return result

    row = await asyncio.to_thread(_fetch_ad_sync)

    if not row:
        await message.answer(f"❌ ID={ad_id} топилмади.")
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

    def _delete_ad_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM ads WHERE id = {p}", (ad_id,))
        conn.commit()
        conn.close()

    await asyncio.to_thread(_delete_ad_sync)

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
    await state.set_state(AdminStates.del_user_ads_id)
    await message.answer(
        "📋 Фойдаланувчи USER_ID сини киритинг:",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.del_user_ads_id)
async def do_del_user_ads(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.ads_menu)
        await message.answer("📋 Эълонлар бошқариши", reply_markup=admin_ads_keyboard())
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ USER_ID рақам бўлиши керак!")
        return

    def _fetch_user_ads_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM ads WHERE user_id = {p}", (user_id,))
        ads_count = cursor.fetchone()[0]

        if ads_count == 0:
            conn.close()
            return ads_count, []

        cursor.execute(f"SELECT msg_id FROM ads WHERE user_id = {p}", (user_id,))
        msg_id_rows = cursor.fetchall()
        conn.close()
        return ads_count, msg_id_rows

    count, all_msg_ids = await asyncio.to_thread(_fetch_user_ads_sync)

    if count == 0:
        await message.answer(f"❌ USER_ID={user_id} учун эълонлар топилмади.")
        return

    deleted_count = 0
    for (msg_ids_str,) in all_msg_ids:
        msg_ids = [int(mid) for mid in str(msg_ids_str).split(",") if mid.strip().isdigit()]
        for msg_id in msg_ids:
            try:
                await bot.delete_message(chat_id=CHANNEL_ID, message_id=msg_id)
                deleted_count += 1
            except Exception:
                pass

    def _delete_user_ads_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM ads WHERE user_id = {p}", (user_id,))
        conn.commit()
        conn.close()

    await asyncio.to_thread(_delete_user_ads_sync)

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
    await state.set_state(AdminStates.add_price_animal)
    await message.answer(
        "🐾 Ҳайвон турини киритинг (кириллда):\n"
        f"Рўхат: {', '.join(VALID_ANIMALS)}",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.add_price_animal)
async def add_price_animal(message: types.Message, state: FSMContext):
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

    def _add_price_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO market_prices (user_id, animal_type, region, price)
            VALUES ({p}, {p}, {p}, {p})
        """, (message.from_user.id, animal, region, price))
        conn.commit()
        conn.close()

    await asyncio.to_thread(_add_price_sync)

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
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    lines = message.text.strip().split("\n")

    def _add_multi_prices_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()

        added = 0
        line_errors = []

        for line in lines:
            parts = line.strip().split()
            if len(parts) < 3:
                line_errors.append(f"❌ `{line.strip()}` — format xato")
                continue

            animal = validate_animal(parts[0])
            region = validate_region(parts[1])

            if animal is None:
                line_errors.append(f"❌ `{parts[0]}` — ҳайвон нотўғри")
                continue
            if region is None:
                line_errors.append(f"❌ `{parts[1]}` — вилоят нотўғри")
                continue

            try:
                price = int(parts[2].replace(" ", ""))
            except ValueError:
                line_errors.append(f"❌ `{line.strip()}` — нарх хато")
                continue

            if price < 1000:
                line_errors.append(f"❌ `{line.strip()}` — нарх кичик")
                continue

            cursor.execute(f"""
                INSERT INTO market_prices (user_id, animal_type, region, price)
                VALUES ({p}, {p}, {p}, {p})
            """, (message.from_user.id, animal, region, price))
            added += 1

        conn.commit()
        conn.close()
        return added, line_errors

    success, errors = await asyncio.to_thread(_add_multi_prices_sync)

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
    def _fetch_prices_sync():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, animal_type, region, price, created_at
            FROM market_prices ORDER BY created_at DESC LIMIT 100
        """)
        result = cursor.fetchall()
        conn.close()
        return result

    rows = await asyncio.to_thread(_fetch_prices_sync)

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
    await state.set_state(AdminStates.del_price_id)
    await message.answer("📋 Нарх ID сини киритинг:", reply_markup=standard_step_keyboard())


@router.message(AdminStates.del_price_id)
async def do_del_price(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    try:
        price_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ ID рақам бўлиши керак!")
        return

    def _delete_price_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, animal_type, region, price FROM market_prices WHERE id = {p}", (price_id,))
        result = cursor.fetchone()

        if result:
            cursor.execute(f"DELETE FROM market_prices WHERE id = {p}", (price_id,))
            conn.commit()
        conn.close()
        return result

    row = await asyncio.to_thread(_delete_price_sync)

    if not row:
        await message.answer(f"❌ ID={price_id} топилмади.")
        return

    _, animal, region, price = row

    await message.answer(
        f"🗑 *Ўчирилди!*\n\n🆔 ID: {price_id}\n🐾 {animal}\n📍 {region}\n💰 {price:,} сўм",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.prices_menu)
    await message.answer("💰 Давом этинг:", reply_markup=admin_prices_keyboard())


# ── Ҳайвон бўйича ўчириш ──

@router.message(AdminStates.prices_menu, F.text == "🗑 Ҳайвон бўйича ўчириш")
async def ask_del_animal(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.del_animal_name)
    await message.answer(
        f"🐾 Ҳайвон турини киритинг:\nРўхат: {', '.join(VALID_ANIMALS)}",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.del_animal_name)
async def do_del_animal(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    animal = validate_animal(message.text.strip())
    if animal is None:
        await message.answer(f"⚠️ Нотўғри: {message.text}")
        return

    def _delete_by_animal_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM market_prices WHERE animal_type = {p}", (animal,))
        cnt = cursor.fetchone()[0]

        if cnt > 0:
            cursor.execute(f"DELETE FROM market_prices WHERE animal_type = {p}", (animal,))
            conn.commit()
        conn.close()
        return cnt

    count = await asyncio.to_thread(_delete_by_animal_sync)

    if count == 0:
        await message.answer(f"❌ *{animal}* учун нархлар топилмади.")
        return

    await message.answer(f"🗑 *{animal}* — {count} та нарх ўчирилди.", parse_mode="Markdown")
    await state.set_state(AdminStates.prices_menu)
    await message.answer("💰 Давом этинг:", reply_markup=admin_prices_keyboard())


# ── Вилоят бўйича ўчириш ──

@router.message(AdminStates.prices_menu, F.text == "🗑 Вилоят бўйича ўчириш")
async def ask_del_region(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.del_region_name)
    await message.answer(
        f"📍 Вилоятни киритинг:\nРўхат: {', '.join(VALID_REGIONS)}",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.del_region_name)
async def do_del_region(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.prices_menu)
        await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
        return

    region = validate_region(message.text.strip())
    if region is None:
        await message.answer(f"⚠️ Нотўғри: {message.text}")
        return

    def _delete_by_region_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM market_prices WHERE region = {p}", (region,))
        cnt = cursor.fetchone()[0]

        if cnt > 0:
            cursor.execute(f"DELETE FROM market_prices WHERE region = {p}", (region,))
            conn.commit()
        conn.close()
        return cnt

    count = await asyncio.to_thread(_delete_by_region_sync)

    if count == 0:
        await message.answer(f"❌ *{region}* учун нархлар топилмади.")
        return

    await message.answer(f"🗑 *{region}* — {count} та нарх ўчирилди.", parse_mode="Markdown")
    await state.set_state(AdminStates.prices_menu)
    await message.answer("💰 Давом этинг:", reply_markup=admin_prices_keyboard())


# ── Барчасини ўчириш ──

@router.message(AdminStates.prices_menu, F.text == "🗑 Барчасини ўчириш")
async def ask_clear_prices(message: types.Message, state: FSMContext):
    def _count_prices_sync():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM market_prices")
        cnt = cursor.fetchone()[0]
        conn.close()
        return cnt

    count = await asyncio.to_thread(_count_prices_sync)

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


@router.message(Command("clearprices_confirm"))
async def do_clear_prices(message: types.Message, state: FSMContext):
    def _clear_prices_sync():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM market_prices")
        cnt = cursor.fetchone()[0]
        if cnt > 0:
            cursor.execute("DELETE FROM market_prices")
            conn.commit()
        conn.close()
        return cnt

    count = await asyncio.to_thread(_clear_prices_sync)

    if count == 0:
        await message.answer("❌ Базада нархлар йўқ.")
        return

    await message.answer(f"🗑 Барчаси ўчирилди — *{count} та* нарх маълумоти.", parse_mode="Markdown")
    await state.set_state(AdminStates.prices_menu)
    await message.answer("💰 Давом этинг:", reply_markup=admin_prices_keyboard())


# ═══════════════════════════════════════
# 🚫 БЛОК МЕНЮСИ
# ═══════════════════════════════════════

@router.message(AdminStates.menu, F.text == "🚫 Блок")
async def admin_block_menu(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.block_menu)
    await message.answer(
        "🚫 *Блок бошқариши*",
        parse_mode="Markdown",
        reply_markup=admin_block_keyboard()
    )


@router.message(AdminStates.block_menu, F.text == "🚫 Блокланганлар рўйхати")
async def show_blocked(message: types.Message, state: FSMContext):
    blocked = await get_blocked_users()
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
    await state.set_state(AdminStates.unblock_id)
    await message.answer("📋 USER_ID киритинг:", reply_markup=standard_step_keyboard())


@router.message(AdminStates.unblock_id)
async def do_unblock(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.block_menu)
        await message.answer("🚫 Блок бошқариши", reply_markup=admin_block_keyboard())
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ USER_ID рақам бўлиши керак!")
        return

    await unblock_user(user_id)
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
    await state.set_state(AdminStates.premium_menu)
    await message.answer(
        "💎 *Премиум бошқариши*",
        parse_mode="Markdown",
        reply_markup=admin_premium_keyboard()
    )


@router.message(AdminStates.premium_menu, F.text == "💎 Премиум бериш")
async def ask_premium_give(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.premium_give_id)
    await message.answer("📋 USER_ID киритинг:", reply_markup=standard_step_keyboard())


@router.message(AdminStates.premium_give_id)
async def do_premium_give(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.premium_menu)
        await message.answer("💎 Премиум бошқариши", reply_markup=admin_premium_keyboard())
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ USER_ID рақам бўлиши керак!")
        return

    def _give_premium_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT full_name, username, is_premium FROM users WHERE user_id = {p}", (user_id,))
        result_row = cursor.fetchone()

        if not result_row:
            conn.close()
            return "not_found", None, None

        full_name_v, username_v, already_premium_v = result_row
        if already_premium_v:
            conn.close()
            return "already_premium", full_name_v, username_v

        if __import__('os').getenv("DATABASE_URL"):
            cursor.execute(f"UPDATE users SET is_premium = TRUE WHERE user_id = {p}", (user_id,))
        else:
            cursor.execute(f"UPDATE users SET is_premium = 1 WHERE user_id = {p}", (user_id,))
        conn.commit()
        conn.close()
        return "updated", full_name_v, username_v

    status, full_name, username = await asyncio.to_thread(_give_premium_sync)

    if status == "not_found":
        await message.answer(f"❌ USER_ID={user_id} базада топилмади.")
        return

    if status == "already_premium":
        await message.answer(f"ℹ️ `{user_id}` аллақачон Премиум.", parse_mode="Markdown")
        return

    uname = f"@{username}" if username else "—"
    safe_name = html.escape(full_name or '—')
    await message.answer(
        f"💎 <b>Премиум берилди!</b>\n\n👤 {safe_name} ({uname})\n🆔 <code>{user_id}</code>",
        parse_mode="HTML"
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
    await state.set_state(AdminStates.premium_remove_id)
    await message.answer("📋 USER_ID киритинг:", reply_markup=standard_step_keyboard())


@router.message(AdminStates.premium_remove_id)
async def do_premium_remove(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.premium_menu)
        await message.answer("💎 Премиум бошқариши", reply_markup=admin_premium_keyboard())
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ USER_ID рақам бўлиши керак!")
        return

    def _remove_premium_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        if __import__('os').getenv("DATABASE_URL"):
            cursor.execute(f"UPDATE users SET is_premium = FALSE WHERE user_id = {p}", (user_id,))
        else:
            cursor.execute(f"UPDATE users SET is_premium = 0 WHERE user_id = {p}", (user_id,))
        conn.commit()
        conn.close()

    await asyncio.to_thread(_remove_premium_sync)

    await message.answer(f"✅ `{user_id}` дан Премиум олиб ташланди.", parse_mode="Markdown")
    await state.set_state(AdminStates.premium_menu)
    await message.answer("💎 Давом этинг:", reply_markup=admin_premium_keyboard())


@router.message(AdminStates.premium_menu, F.text == "💎 Премиум рўйхати")
async def show_premium_list(message: types.Message, state: FSMContext):
    def _fetch_premium_list_sync():
        conn = get_connection()
        cursor = conn.cursor()
        if __import__('os').getenv("DATABASE_URL"):
            cursor.execute("SELECT user_id, full_name, username FROM users WHERE is_premium = TRUE ORDER BY user_id")
        else:
            cursor.execute("SELECT user_id, full_name, username FROM users WHERE is_premium = 1 ORDER BY user_id")
        result = cursor.fetchall()
        conn.close()
        return result

    rows = await asyncio.to_thread(_fetch_premium_list_sync)

    if not rows:
        await message.answer("💎 Ҳозирча Премиум аъзолар йўқ.")
        return

    text = f"💎 <b>Премиум аъзолар ({len(rows)} та):</b>\n\n"
    for uid, full_name, username in rows:
        uname = f"@{username}" if username else "—"
        safe_name = html.escape(full_name or '—')
        text += f"👤 {safe_name} ({uname}) — <code>{uid}</code>\n"
    await message.answer(text, parse_mode="HTML")


# ═══════════════════════════════════════
# 📢 ТАРҚАТИШ
# ═══════════════════════════════════════

@router.message(AdminStates.menu, F.text == "📢 Тарқатиш")
async def ask_broadcast(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.broadcast_text)
    await message.answer(
        "📢 Юбориладиган матнни ёзинг:",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdminStates.broadcast_text)
async def do_broadcast(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(AdminStates.menu)
        await message.answer("🔐 Админ панел", reply_markup=admin_menu_keyboard())
        return

    broadcast_text = message.text.strip()
    if not broadcast_text:
        await message.answer("⚠️ Матн бўш.")
        return

    def _fetch_all_users_sync():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        result = cursor.fetchall()
        conn.close()
        return result

    users = await asyncio.to_thread(_fetch_all_users_sync)

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
    db_url = __import__('os').getenv("DATABASE_URL", "")
    
    stats = await get_full_statistics()

    def _fetch_user_stats_sync():
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]

        if db_url:
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = TRUE")
        else:
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
        premium = cursor.fetchone()[0]

        if db_url:
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = TRUE")
        else:
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
        blocked_count = cursor.fetchone()[0]

        conn.close()
        return total, premium, blocked_count

    total_users, premium_users, blocked = await asyncio.to_thread(_fetch_user_stats_sync)

    active_users = total_users - blocked

    text = "📈 *БОТ СТАТИСТИКАСИ*\n"
    text += f"{'═' * 28}\n\n"
    text += f"👥 *ФОЙДАЛАНУВЧИЛАР:*\n"
    text += f"  📋 Жами: *{total_users}* та\n"
    text += f"  💎 Премиум: *{premium_users}* та\n"
    text += f"  🚫 Блокланган: *{blocked}* та\n"
    text += f"  ✅ Хабар олиш мумкин: *{active_users}* та\n\n"

    text += f"📋 *ЭЪЛОНЛАР:*\n"
    text += f"  Жами: *{stats['total_ads']}* та\n"
    text += f"  ✅ Фаол: *{stats['active_ads']}* та\n"
    text += f"  🤝 Сотилган: *{stats['sold_ads']}* та\n"
    text += f"  📊 Нархлар: *{stats['market_price_entries']}* та\n\n"

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
    def _check_prices_sync():
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, animal_type, region, price FROM ads WHERE status = 'active'")
        ads_rows = cursor.fetchall()

        cursor.execute("SELECT id, animal_type, region, price FROM market_prices")
        mp_rows = cursor.fetchall()

        conn.close()
        return ads_rows, mp_rows

    ads, mp = await asyncio.to_thread(_check_prices_sync)
    zero_ads = [f"🆔{r[0]} | {r[1]} | {r[2]} | `{r[3]}`" for r in ads if parse_price_text(str(r[3])) == 0]
    zero_mp = [f"🆔{r[0]} | {r[1]} | {r[2]} | `{r[3]}`" for r in mp if r[3] is None or r[3] == 0]

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
    
