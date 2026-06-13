import asyncio
import html
import sqlite3

from aiogram import Router, types
from aiogram.filters import Command

from config import bot, ADMINS
from database import get_full_statistics, fmt_number

router = Router()


# ═══════════════════════════════════════
# KIRILL TEKSHIRISH
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
# 1. /addprice — Bitta narx qo'shish
# ═══════════════════════════════════════

@router.message(Command("addprice"))
async def admin_add_price(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Сизга рухсат йўқ.")
        return

    parts = message.text.split(maxsplit=3)

    if len(parts) < 4:
        await message.answer(
            "📋 *Format:*\n"
            "`/addprice Сигир Тошкент 15000000`\n\n"
            "⚠️ *Фақат кириллда ёзинг!*\n"
            "Рўхат: /adminhelp",
            parse_mode="Markdown"
        )
        return

    animal = validate_animal(parts[1])
    region = validate_region(parts[2])

    if animal is None:
        await message.answer(
            f"⚠️ *Ҳайвон тури нотўғри:* `{parts[1]}`\n\n"
            f"*Рўхатдан танланг:*\n"
            f"Буқа, Сигир, Тана, Бузоқ, Қўй, Қўчқор,\n"
            f"Совлиқ, Қўзи, Эчки, Улоқ, От, Туя,\n"
            f"Парранда\n\n"
            f"⚠️ *Фақат кириллда ёзинг!*",
            parse_mode="Markdown"
        )
        return

    if region is None:
        await message.answer(
            f"⚠️ *Вилоят нотўғри:* `{parts[2]}`\n\n"
            f"*Рўхатдан танланг:*\n"
            f"Қашқадарё, Сурхондарё, Тошкент, Фарғона,\n"
            f"Андижон, Наманган, Самарқанд, Бухоро,\n"
            f"Навоий, Жиззах, Сирдарё, Хоразм,\n"
            f"Қорақалпоғистон\n\n"
            f"⚠️ *Фақат кириллда ёзинг!*",
            parse_mode="Markdown"
        )
        return

    try:
        price = int(parts[3].replace(" ", ""))
    except ValueError:
        await message.answer("⚠️ Нарх рақам бўлиши керак!")
        return

    if price < 1000:
        await message.answer("⚠️ Нарх жуда кичик!")
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO market_prices (user_id, animal_type, region, price)
        VALUES (?, ?, ?, ?)
    """, (message.from_user.id, animal, region, price))
    conn.commit()
    conn.close()

    await message.answer(
        f"✅ *Нарх киритилди!*\n\n"
        f"🐾 {animal}\n"
        f"📍 {region}\n"
        f"💰 {price:,} so'm\n\n"
        f"Кўриш: /viewprices",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════
# 2. /addmulti — Ko'p narx qo'shish
# ═══════════════════════════════════════

@router.message(Command("addmulti"))
async def admin_add_multi(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Сизга рухсат йўқ.")
        return

    lines = message.text.strip().split("\n")

    if len(lines) < 2:
        await message.answer(
            "📋 *Format:*\n\n"
            "`/addmulti\n"
            "Сигир Тошкент 15000000\n"
            "Қўй Самарқанд 3500000\n"
            "Эчки Фарғона 2800000`\n\n"
            "⚠️ *Фақат кириллда ёзинг!*",
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

        animal = validate_animal(parts[0])
        region = validate_region(parts[1])

        if animal is None:
            errors.append(f"❌ `{parts[0]}` — ҳайвон нотўғри (кириллда ёзинг)")
            continue

        if region is None:
            errors.append(f"❌ `{parts[1]}` — вилоят нотўғри (кириллда ёзинг)")
            continue

        try:
            price = int(parts[2].replace(" ", ""))
        except ValueError:
            errors.append(f"❌ `{line.strip()}` — нарх хато")
            continue

        if price < 1000:
            errors.append(f"❌ `{line.strip()}` — нарх кичик")
            continue

        cursor.execute("""
            INSERT INTO market_prices (user_id, animal_type, region, price)
            VALUES (?, ?, ?, ?)
        """, (message.from_user.id, animal, region, price))
        success += 1

    conn.commit()
    conn.close()

    text = f"✅ *{success} та нарх киритилди!*\n"
    if errors:
        text += f"\n❌ *Хатолар ({len(errors)}):*\n"
        text += "\n".join(errors[:10])

    await message.answer(text, parse_mode="Markdown")


# ═══════════════════════════════════════
# 3. /viewprices — Narxlarni ko'rish (ID bilan)
# ═══════════════════════════════════════

@router.message(Command("viewprices"))
async def admin_view_prices(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Сизга рухсат йўқ.")
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, animal_type, region, price, created_at
        FROM market_prices ORDER BY created_at DESC LIMIT 100
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "❌ Базада нархлар йўқ.\n\nКиритиш: /addprice yoki /addmulti"
        )
        return

    text = f"📊 *Базадаги нархлар ({len(rows)} та):*\n\n"
    text += f"_Ўчириш учун: /delprice ID raqami_\n\n"

    for row_id, animal, region, price, date in rows:
        text += f"🆔 `{row_id}` — 🐾 *{animal}* | 📍 {region} | 💰 {price:,} so'm\n"

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


# ═══════════════════════════════════════
# 4. /delprice — Bitta narxni o'chirish
# ═══════════════════════════════════════

@router.message(Command("delprice"))
async def admin_del_price(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Сизга рухсат йўқ.")
        return

    parts = message.text.split()

    if len(parts) < 2:
        await message.answer(
            "📋 *Format:*\n"
            "`/delprice ID`\n\n"
            "*Мисол:* `/delprice 5`\n\n"
            "ID ни билиш учун: /viewprices",
            parse_mode="Markdown"
        )
        return

    try:
        price_id = int(parts[1])
    except ValueError:
        await message.answer("⚠️ ID рақам бўлиши керак!")
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, animal_type, region, price FROM market_prices WHERE id = ?",
        (price_id,)
    )
    row = cursor.fetchone()

    if not row:
        await message.answer(f"❌ ID={price_id} топилмади.")
        conn.close()
        return

    _, animal, region, price = row

    cursor.execute("DELETE FROM market_prices WHERE id = ?", (price_id,))
    conn.commit()
    conn.close()

    await message.answer(
        f"🗑 *Ўчирилди!*\n\n"
        f"🆔 ID: {price_id}\n"
        f"🐾 {animal}\n"
        f"📍 {region}\n"
        f"💰 {price:,} сўм",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════
# 5. /delanimal — Hayvon turi bo'yicha o'chirish
# ═══════════════════════════════════════

@router.message(Command("delanimal"))
async def admin_del_animal(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Сизга рухсат йўқ.")
        return

    parts = message.text.split()

    if len(parts) < 2:
        await message.answer(
            "📋 *Формат:*\n"
            "`/delanimal Ҳайвонтури`\n\n"
            "*Мисол:* `/delanimal Сигир`\n\n"
            "⚠️ *Фақат кириллда ёзинг!*\n"
            f"*Рўйхат:* {', '.join(VALID_ANIMALS)}",
            parse_mode="Markdown"
        )
        return

    animal = validate_animal(parts[1])

    if animal is None:
        await message.answer(
            f"⚠️ *Ҳайвон тури нотўғри:* `{parts[1]}`\n\n"
            f"*Рўйхатдан танланг:*\n"
            f"{', '.join(VALID_ANIMALS)}\n\n"
            f"⚠️ *Фақат кириллда ёзинг!*",
            parse_mode="Markdown"
        )
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM market_prices WHERE animal_type = ?",
        (animal,)
    )
    count = cursor.fetchone()[0]

    if count == 0:
        await message.answer(f"❌ *{animal}* учун нархлар топилмади.")
        conn.close()
        return

    cursor.execute(
        "DELETE FROM market_prices WHERE animal_type = ?",
        (animal,)
    )
    conn.commit()
    conn.close()

    await message.answer(
        f"🗑 *{animal}* — {count} та нарх ўчирилди.",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════
# 6. /delregion — Viloyat bo'yicha o'chirish
# ═══════════════════════════════════════

@router.message(Command("delregion"))
async def admin_del_region(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Сизга рухсат йўқ.")
        return

    parts = message.text.split()

    if len(parts) < 2:
        await message.answer(
            "📋 *Формат:*\n"
            "`/delregion Вилоят`\n\n"
            "*Мисол:* `/delregion Тошкент`\n\n"
            "⚠️ *Фақат кириллда ёзинг!*\n"
            f"*Рўйхат:* {', '.join(VALID_REGIONS)}",
            parse_mode="Markdown"
        )
        return

    region = validate_region(parts[1])

    if region is None:
        await message.answer(
            f"⚠️ *Вилоят нотўғри:* `{parts[1]}`\n\n"
            f"*Рўйхатдан танланг:*\n"
            f"{', '.join(VALID_REGIONS)}\n\n"
            f"⚠️ *Фақат кириллда ёзинг!*",
            parse_mode="Markdown"
        )
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM market_prices WHERE region = ?",
        (region,)
    )
    count = cursor.fetchone()[0]

    if count == 0:
        await message.answer(f"❌ *{region}* учун нархлар топилмади.")
        conn.close()
        return

    cursor.execute(
        "DELETE FROM market_prices WHERE region = ?",
        (region,)
    )
    conn.commit()
    conn.close()

    await message.answer(
        f"🗑 *{region}* — {count} та нарх ўчирилди.",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════
# 7. /clearprices — HAMMA narxni o'chirish (tasdiqlash bilan)
# ═══════════════════════════════════════

@router.message(Command("clearprices"))
async def admin_clear_prices(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Сизга рухсат йўқ.")
        return

    conn = sqlite3.connect("chorva.db")
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
        f"Ишончингиз комил бўлса:\n"
        f"`/clearprices_confirm`\n\n"
        f"Бекор қилиш учун ҳеч нарса ёзманг.",
        parse_mode="Markdown"
    )


@router.message(Command("clearprices_confirm"))
async def admin_clear_prices_confirm(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Сизга рухсат йўқ.")
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM market_prices")
    count = cursor.fetchone()[0]

    if count == 0:
        await message.answer("❌ Базада нархлар йўқ.")
        conn.close()
        return

    cursor.execute("DELETE FROM market_prices")
    conn.commit()
    conn.close()

    await message.answer(f"🗑 *{count} та* нарх ўчирилди.", parse_mode="Markdown")


# ═══════════════════════════════════════
# 8. /broadcast_users — Xabar tarqatish
# ═══════════════════════════════════════

@router.message(Command("broadcast_users"))
async def broadcast_to_users(message: types.Message):
    if message.from_user.id not in ADMINS:
        return

    command_len = len("/broadcast_users")
    broadcast_text = message.text[command_len:].strip()

    if not broadcast_text:
        await message.answer(
            "⚠️ Илтимос, буйруқдан кейин тарқатиладиган матнни ёзинг.\n\n"
            "Масалан:\n`/broadcast_users Салом ҳаммага`",
            parse_mode="Markdown"
        )
        return

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

    status_message = await message.answer(
        f"⏳ Хабар юбориш бошланди (Жами: {len(users)} та фойдаланувчи)..."
    )

    for user in users:
        uid = user[0]
        try:
            await bot.send_message(chat_id=uid, text=broadcast_text)
            sent_count += 1
        except Exception:
            try:
                escaped = html.escape(broadcast_text)
                await bot.send_message(chat_id=uid, text=escaped)
                sent_count += 1
            except Exception:
                failed_count += 1
        await asyncio.sleep(0.05)

    await status_message.edit_text(
        f"📢 **Тарқатиш якунланди!**\n\n"
        f"✅ Муваффақиятли: {sent_count} та\n"
        f"❌ Юборилмади: {failed_count} та",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════
# 9. /stats — Bot statistikasi
# ═══════════════════════════════════════

@router.message(Command("stats"))
async def admin_stats(message: types.Message):
    if message.from_user.id not in ADMINS:
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

    await message.answer(text, parse_mode="Markdown")


# ═══════════════════════════════════════
# 10. /adminhelp — Yordam
# ═══════════════════════════════════════

@router.message(Command("adminhelp"))
async def admin_help(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Сизга рухсат йўқ.")
        return

    await message.answer(
        "🔐 *ADMIN BUYRUQLARI:*\n\n"

        "📝 *Нарх қўшиш:*\n"
        "`/addprice Сигир Тошкент 15000000`\n"
        "— битта нарх\n\n"
        "`/addmulti`\n"
        "Сигир Тошкент 15000000\n"
        "Қўй Самарқанд 3500000\n"
        "— кўп нархни бир вақтда\n\n"

        "👀 *Кўриш:*\n"
        "`/viewprices` — нархлар (ID билан)\n\n"

        "🗑 *О'чириш:*\n"
        "`/delprice 5` — ID бўйича битта\n"
        "`/delanimal Сигир` — ҳайвон тури бўйича\n"
        "`/delregion Тошкент` — вилоят бўйича\n"
        "`/clearprices` — барчасини (тасдиқлаш билан)\n\n"

        "📢 *Хабар:*\n"
        "`/broadcast_users матн` — фойдаланувчиларга\n\n"

        "👥 *Статистика:*\n"
        "`/stats` — бот статистикаси\n\n"

        "ℹ️ *Ёрдам:*\n"
        "`/adminhelp` — шу хабар\n\n"

        "⚠️ *Нарх киритишда ФАҚАТ КИРИЛЛ алифбосидан фойдаланинг!*\n\n"

        "*Ҳайвонлар:*\n"
        "Буқа, Сигир, Тана, Бузоқ, Қўй, Қўчқор,\n"
        "Совлиқ, Қўзи, Эчки, Улоқ, От, Туя,\n"
        "Парранда\n\n"

        "*Вилоятлар:*\n"
        "Қашқадарё, Сурхондарё, Тошкент, Фарғона,\n"
        "Андижон, Наманган, Самарқанд, Бухоро,\n"
        "Навоий, Жиззах, Сирдарё, Хоразм,\n"
        "Қорақалпоғистон",
        parse_mode="Markdown"
    )
