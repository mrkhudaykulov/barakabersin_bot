"""
channel_check.py

Эълон беришдан олдин фойдаланувчи профилига бириктирилган ШАХСИЙ
КАНАЛни (Telegram'нинг "Personal chat" функцияси) текширади. Агар
каналнинг номи/username'ида очиқ 18+ белгиси топилса, фойдаланувчи
дарҳол блокланади — худди ножўя сўз текшируви каби.

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
from database import contains_bad_word, contains_adult_keyword, block_for_adult_channel


async def check_personal_channel_and_maybe_block(user_id: int, ad_id: int = None) -> bool:
    """
    Фойдаланувчининг профилига бириктирилган шахсий канали (агар бор
    бўлса) номида 18+ калит сўзи топилса — дарҳол блоклайди.

    Қайтаради: True — блокланди (чақирувчи эълонни рад этиши керак),
               False — хавфсиз ёки текшириб бўлмади (давом этавериш мумкин).
    """
    try:
        chat = await bot.get_chat(user_id)
    except Exception as e:
        # Профиль ўқилмаса (тармоқ, рухсат ва ҳ.к.) — текширувни
        # ўтказиб юборамиз, эълон беришни тўсмаймиз.
        logging.info("Профиль (шахсий канал) текширилмади (user_id=%s): %s", user_id, e)
        return False

    personal = getattr(chat, "personal_chat", None)
    if not personal:
        return False

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
