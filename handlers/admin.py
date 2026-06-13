import asyncio
import html
import sqlite3

from aiogram import Router, types
from aiogram.filters import Command

from config import bot, ADMINS

router = Router()


@router.message(Command("addprice"))
async def admin_add_price(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Sizga ruxsat yo'q.")
        return

    parts = message.text.split(maxsplit=3)

    if len(parts) < 4:
        await message.answer(
            "📋 *Format:*\n"
            "`/addprice Hayvon Viloyat Narx`\n\n"
            "*Misol:*\n"
            "`/addprice Sigir Toshkent 15000000`",
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
        INSERT INTO market_prices (user_id, animal_type, region, price)
        VALUES (?, ?, ?, ?)
    """, (message.from_user.id, animal, region, price))
    conn.commit()
    conn.close()

    await message.answer(
        f"✅ *Narx kiritildi!*\n\n"
        f"🐾 {animal}\n📍 {region}\n💰 {price:,} so'm\n\n"
        f"Ko'rish: /viewprices",
        parse_mode="Markdown"
    )


@router.message(Command("addmulti"))
async def admin_add_multi(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Sizga ruxsat yo'q.")
        return

    lines = message.text.strip().split("\n")

    if len(lines) < 2:
        await message.answer(
            "📋 *Format:*\n\n"
            "`/addmulti\nSigir Toshkent 15000000\n"
            "Qoy Samarqand 3500000`",
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
            INSERT INTO market_prices (user_id, animal_type, region, price)
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


@router.message(Command("viewprices"))
async def admin_view_prices(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Sizga ruxsat yo'q.")
        return

    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT animal_type, region, price, created_at
        FROM market_prices ORDER BY created_at DESC LIMIT 100
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "❌ Bazada narxlar yo'q.\n\nKiritish: /addprice yoki /addmulti"
        )
        return

    grouped = {}
    for animal, region, price, date in rows:
        if animal not in grouped:
            grouped[animal] = []
        grouped[animal].append((region, price))

    text = f"📊 *Bazadagi narxlar ({len(rows)} ta):*\n\n"

    for animal, items in grouped.items():
        text += f"🐾 *{animal}:*\n"
        seen = set()
        for region, price in items:
            if region not in seen:
                seen.add(region)
                text += f"   📍 {region}: {price:,} so'm\n"
        text += "\n"

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


@router.message(Command("clearprices"))
async def admin_clear_prices(message: types.Message):
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


@router.message(Command("adminhelp"))
async def admin_help(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Sizga ruxsat yo'q.")
        return

    await message.answer(
        "🔐 *ADMIN BUYRUQLARI:*\n\n"
        "📝 *Narx kiritish:*\n"
        "`/addprice Sigir Toshkent 15000000`\n"
        "`/addmulti` — ko'p narxni bir vaqtda\n\n"
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
