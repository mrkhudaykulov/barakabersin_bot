"""
scheduler.py — Фонда ишлайдиган вазифалар

Вазифалар:
1. Ҳар куни соат 10:00 да муддати 2 кун қолган эълонлар эгасига эслатма
2. Ҳар куни соат 09:00 да муддати 7 кун қолган эълонлар эгасига огоҳлантириш
3. Ҳар соатда муддати ўтган эълонларни 'expired' статусига ўтказиш

Ишга тушириш: main.py дан asyncio.create_task(start_scheduler(bot)) орқали
"""

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import get_expiring_ads, get_expired_ads, archive_ad, contains_bad_word
from config import CHANNEL_ID

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
# ЭСЛАТМА ХАБАРЛАРИ
# ═══════════════════════════════════════

def repost_keyboard(ad_id: int) -> InlineKeyboardMarkup:
    """Фақат 2 кун қолганда кўринади — премиум текшириш ads.py да"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🔄 Каналга қайта жойлаш",
            callback_data=f"repost_{ad_id}"
        ),
        InlineKeyboardButton(
            text="❌ Ўчириш",
            callback_data=f"del_{ad_id}"
        )
    ]])


async def send_expiry_reminder(bot: Bot, days_left: int):
    """
    Муддати days_left кун қолган эълон эгаларига хабар юбориш.
    """
    ads = get_expiring_ads(days_left)
    if not ads:
        logger.info(f"[Scheduler] {days_left} кун қолган эълон йўқ.")
        return

    logger.info(f"[Scheduler] {days_left} кун қолган {len(ads)} та эълон учун эслатма юборилмоқда...")

    for ad in ads:
        ad_id, user_id, animal_type, quantity, price, msg_id = ad
        try:
            if days_left == 2:
                emoji = "🔴"
                urgency = "ОХИРГИ"
                extra = "\n\n⚠️ Муддат ўтса эълон каналдан архивланади!"
            else:
                emoji = "🟡"
                urgency = ""
                extra = ""

            text = (
                f"{emoji} <b>Эълон муддати {urgency} {days_left} кун қолди!</b>\n\n"
                f"📦 <b>{animal_type}</b> — {quantity}\n"
                f"💰 <b>Нарх:</b> {price}\n\n"
                f"💎 <b>Премиум</b> аъзолар эълонни каналга қайта жойлашлари мумкин.{extra}"
            )

            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                reply_markup=repost_keyboard(ad_id)
            )
            # Spam-ga tushmaslik uchun kichik kutish
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.warning(f"[Scheduler] user_id={user_id} га хабар юбориб бўлмади: {e}")


async def archive_expired_ads(bot: Bot):
    """
    Муддати ўтган эълонларни arxivlash va kanal xabarini yangilash.
    """
    ads = get_expired_ads()
    if not ads:
        return

    logger.info(f"[Scheduler] {len(ads)} та муддати ўтган эълон архивланмоқда...")

    for ad in ads:
        ad_id, user_id, animal_type, msg_id = ad
        try:
            # Базада статусни ўзгартириш
            archive_ad(ad_id)

            # Каналдаги хабарни "МУДДАТИ ТУГАДИ" деб белгилаш
            if msg_id:
                first_msg_id = int(str(msg_id).split(",")[0].strip())
                try:
                    await bot.edit_message_caption(
                        chat_id=CHANNEL_ID,
                        message_id=first_msg_id,
                        caption=(
                            f"🗄 <b>МУДДАТИ ТУГАДИ</b>\n\n"
                            f"#{animal_type} эълони архивланди.\n"
                            f"Янги эълон бериш: @barakabersin_bot"
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass  # Хабар ўчирилган бўлиши мумкин

            # Эълон эгасига хабар
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🗄 <b>{animal_type}</b> эълонингиз муддати тугади.\n\n"
                        f"Эълонни янгилаш учун ботдан қайта жойланг.\n"
                        f"👉 /start"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"[Scheduler] ad_id={ad_id} архивлашда хато: {e}")


# ═══════════════════════════════════════
# КУНЛИК ВАҚТ ҲИСОБЛАШ
# ═══════════════════════════════════════

async def seconds_until(hour: int, minute: int = 0) -> float:
    """
    Кейинги target soat:daqiqagacha nechi soniya qolganligi.
    Agar bugun o'tib ketgan bo'lsa — ertangi vaqtgacha.
    """
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        # Эртага
        target = target.replace(day=target.day + 1)
    delta = (target - now).total_seconds()
    return delta


# ═══════════════════════════════════════
# АСОСИЙ SCHEDULER LOOP
# ═══════════════════════════════════════

async def task_2day_reminder(bot: Bot):
    """Ҳар куни соат 10:00 да 2 кун қолган эълонларга огоҳлантириш"""
    while True:
        wait = await seconds_until(hour=10, minute=0)
        logger.info(f"[Scheduler] 2-кун эслатмаси {wait/3600:.1f} соатдан кейин.")
        await asyncio.sleep(wait)
        await send_expiry_reminder(bot, days_left=2)


async def task_archive_expired(bot: Bot):
    """Ҳар куни муддати ўтган эълонларни архивлаш"""
    while True:
        await asyncio.sleep(86400)  # 1 kun
        await archive_expired_ads(bot)


async def start_scheduler(bot: Bot):
    """
    Барча scheduler вазифаларини параллел ишга тушириш.
    main.py дан чақирилади:
        asyncio.create_task(start_scheduler(bot))
    """
    logger.info("[Scheduler] Барча вазифалар ишга тушди.")

    # Бот ишга тушгандаёқ муддати ўтганларни архивлаш
    await archive_expired_ads(bot)

    # Параллел вазифалар
    await asyncio.gather(
        task_7day_reminder(bot),
        task_2day_reminder(bot),
        task_archive_expired(bot),
    )
