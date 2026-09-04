"""
channel_check.py

Эълон беришдан олдин фойдаланувчи ПРОФИЛИНИ 18+ мазмунга текширади:
  1. Ўз исми, фамилияси, nickname'и (username) ва bio'си
  2. Профилга бириктирилган ШАХСИЙ КАНАЛ (Telegram'нинг "Personal chat"
     функцияси) номи/username'и
Иккаласи ҳам bot.get_chat(user_id) орқали БИТТА сўровда олинади.

⚠️ ЧЕКЛОВЛАР (фойдаланувчига айтилган):
  1. Каналнинг ИЧКИ КОНТЕНТИ текширилмайди — фақат номи/username'и.
     Бот ўша каналга аъзо/админ эмас, шунинг учун контентни ўқий олмайди.
  2. Bot API'нинг personal_chat майдони нисбатан янги ва ХАР ДОИМ ҳам
     тўлдирилмаган бўлиши мумкин — бу функция шунчаки мавжуд бўлганида
     фойдаланади, йўқлигини хатолик деб ҳисобламайди.
  3. Калит сўз бўйича қидирув — "xxx" каби қисқа сўзлар баъзан зарарсиз
     номлар ичида ҳам учраши мумкин (масалан "Maxxx"). Фойдаланувчи бу
     хавфни билган ҳолда содда (аниқ) усулни танлади.
"""

import logging

from config import bot
from database import (
    contains_bad_word, contains_adult_keyword,
    block_for_adult_channel, block_for_adult_profile,
)


async def check_profile_and_maybe_block(user_id: int, ad_id: int = None) -> bool:
    """
    Фойдаланувчининг ЎЗ исми/nickname'и/bio'сида, ЁКИ профилига
    бириктирилган шахсий каналининг номи/username'ида 18+ калит сўзи
    топилса — дарҳол блоклайди.

    Қайтаради: True — блокланди (чақирувчи эълонни рад этиши керак),
               False — хавфсиз ёки текшириб бўлмади (давом этавериш мумкин).
    """
    try:
        chat = await bot.get_chat(user_id)
    except Exception as e:
        # Профиль ўқилмаса (тармоқ, рухсат ва ҳ.к.) — текширувни
        # ўтказиб юборамиз, эълон беришни тўсмаймиз.
        logging.info("Профиль текширилмади (user_id=%s): %s", user_id, e)
        return False

    # ═══ 1. ЎЗ ИСМ / NICKNAME / BIO ═══
    first_name = getattr(chat, "first_name", None) or ""
    last_name = getattr(chat, "last_name", None) or ""
    own_username = getattr(chat, "username", None) or ""
    bio = getattr(chat, "bio", None) or ""
    own_combined = " ".join([first_name, last_name, own_username, bio])

    if contains_adult_keyword(own_combined) or contains_bad_word(own_combined):
        detail = f"@{own_username}" if own_username else f"{first_name} {last_name}".strip()
        logging.warning(
            "18+ профиль (исм/nickname) аниқланди: user_id=%s (%s) — блокланди",
            user_id, detail
        )
        await block_for_adult_profile(user_id, detail=detail, ad_id=ad_id)
        return True

    # ═══ 2. ШАХСИЙ КАНАЛ (personal_chat) ═══
    personal = getattr(chat, "personal_chat", None)
    if personal:
        title = personal.title or ""
        username = personal.username or ""
        combined = f"{title} {username}"

        if contains_adult_keyword(combined) or contains_bad_word(combined):
            logging.warning(
                "18+ шахсий канал аниқланди: user_id=%s, канал=%s (@%s) — блокланди",
                user_id, title, username
            )
            await block_for_adult_channel(
                user_id, channel_title=title, channel_username=username, ad_id=ad_id
            )
            return True

    return False
