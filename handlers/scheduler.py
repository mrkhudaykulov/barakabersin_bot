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
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import get_expiring_ads, get_expired_ads, archive_ad, contains_bad_word, AD_EXPIRE_DAYS
from config import CHANNEL_ID
from handlers.ratelimit import fan_out

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


async def send_expiry_reminder(bot: Bot, days_left: int = 2):
    """
    Муддати days_left кун қолган эълон эгаларига хабар юбориш.

    ⚠️ Аввал бу функция days_left аргументини умуман ишлатмасдан доим
    get_expiring_ads(2) чақирарди, устига task_2day_reminder уни
    аргументсиз чақирар эди — яъни ҳар куни соат 10:00 да TypeError
    билан йиқилиб, эслатмалар ҲЕЧ ҚАЧОН юборилмаган.
    """
    ads = await get_expiring_ads(days_left)
    if not ads:
        logger.info(f"[Scheduler] {days_left} кун қолган эълон йўқ.")
        return

    logger.info(
        f"[Scheduler] {days_left} кун қолган {len(ads)} та эълон учун "
        f"эслатма юборилмоқда..."
    )

    if days_left <= 2:
        headline = f"🔴 <b>Эълон муддати ОХИРГИ {days_left} кун қолди!</b>"
    else:
        headline = f"🟡 <b>Эълон муддатига {days_left} кун қолди.</b>"

    async def _remind_one(ad):
        ad_id, user_id, animal_type, quantity, price, msg_id = ad
        text = (
            f"{headline}\n\n"
            f"📦 <b>{animal_type}</b> — {quantity}\n"
            f"💰 <b>Нарх:</b> {price}\n\n"
            f"💎 <b>Премиум</b> аъзолар эълонни "
            f"каналга қайта жойлашлари мумкин."
            f"\n\n⚠️ Муддат ўтса эълон "
            f"каналдан архивланади!"
        )
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=repost_keyboard(ad_id) if days_left <= 2 else None
        )
        return True

    results = await fan_out(_remind_one, ads, description="Муддат эслатмаси")
    logger.info(
        f"[Scheduler] {sum(1 for r in results if r)}/{len(ads)} та эслатма юборилди."
    )


async def archive_expired_ads(bot: Bot):
    """
    Муддати ўтган эълонларни arxivlash va kanal xabarini yangilash.
    """
    ads = await get_expired_ads()
    if not ads:
        return

    logger.info(f"[Scheduler] {len(ads)} та муддати ўтган эълон архивланмоқда...")

    for ad in ads:
        ad_id, user_id, animal_type, msg_id = ad
        try:
            # Базада статусни ўзгартириш
            await archive_ad(ad_id)

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
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


# ═══════════════════════════════════════
# АСОСИЙ SCHEDULER LOOP
# ═══════════════════════════════════════

async def _safe(coro_factory, name: str):
    """
    Вазифанинг бир мартаlik ишини хатоликдан ҳимоялайди — акс ҳолда
    битта хатолик бутун цикл вазифасини (ва у билан бирга кундалик
    эслатмаларни) бутунлай ўлдирар эди.
    """
    try:
        await coro_factory()
    except Exception:
        logger.exception(f"[Scheduler] '{name}' вазифасида хатолик")


async def task_daily_reminders(bot: Bot):
    """
    Ҳар куни соат 09:00 да 7 кун қолганларга,
    соат 10:00 да эса 2 кун қолганларга огоҳлантириш.
    """
    while True:
        wait_7 = await seconds_until(hour=9, minute=0)
        wait_2 = await seconds_until(hour=10, minute=0)

        if wait_7 <= wait_2:
            logger.info(f"[Scheduler] 7-кун эслатмаси {wait_7/3600:.1f} соатдан кейин.")
            await asyncio.sleep(wait_7)
            await _safe(lambda: send_expiry_reminder(bot, days_left=7), "7-кун эслатмаси")
        else:
            logger.info(f"[Scheduler] 2-кун эслатмаси {wait_2/3600:.1f} соатдан кейин.")
            await asyncio.sleep(wait_2)
            await _safe(lambda: send_expiry_reminder(bot, days_left=2), "2-кун эслатмаси")

        # Бир xil дақиқада иккинчи марта ишламаслиги учун
        await asyncio.sleep(61)


async def task_archive_expired(bot: Bot):
    """Ҳар куни муддати ўтган эълонларни архивлаш"""
    while True:
        await asyncio.sleep(7200)  # 2 соат
        await _safe(lambda: archive_expired_ads(bot), "Архивлаш")


async def start_scheduler(bot: Bot):
    """
    Барча scheduler вазифаларини параллел ишга тушириш.
    main.py дан чақирилади:
        asyncio.create_task(start_scheduler(bot))
    """
    logger.info("[Scheduler] Барча вазифалар ишга тушди.")

    # Бот ишга тушгандаёқ муддати ўтганларни архивлаш
    await _safe(lambda: archive_expired_ads(bot), "Бошланғич архивлаш")

    # Параллел вазифалар — биттаси йиқилса, бошқаси давом этсин
    await asyncio.gather(
        task_daily_reminders(bot),
        task_archive_expired(bot),
        return_exceptions=True,
    )
