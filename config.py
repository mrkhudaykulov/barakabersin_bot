import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    # Акс ҳолда хатолик aiogram ичида тушунарсиз traceback билан чиқади
    # (ёки Mini App backend'и ҳар бир сўровда 500 беради) — сабабини
    # деплой логидан топиш қийин бўлади.
    raise RuntimeError(
        "BOT_TOKEN муҳит ўзгарувчиси (environment variable) ўрнатилмаган! "
        "Render'да Environment бўлимига ёки локал .env файлига BOT_TOKEN=... қўшинг."
    )


def _env_ids(name: str, default: list[int]) -> list[int]:
    """
    Вергул билан ажратилган ID рўйхатини муҳит ўзгарувчисидан ўқийди.
    Ўрнатилмаган бўлса — коддаги стандарт рўйхат ишлатилади (эски хулқ).
    """
    raw = os.getenv(name)
    if not raw:
        return default
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            logging.warning("%s ичидаги '%s' сон эмас — ўтказиб юборилди.", name, part)
    return ids or default


CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1001419724490"))

# Админ ID лари — бир неча одам бўлиши mumkin
ADMINS = _env_ids("ADMINS", [72185847])

# Тасдиқловчи админлар (шулардан биттаси тасдиқлайди)
REVIEW_ADMINS = _env_ids("REVIEW_ADMINS", [72185847, 2134695872])

DATABASE_URL = os.getenv("DATABASE_URL") # PostgreSQL yoki SQLite

# Mini App учун асосий манзил — Render'даги сизнинг реал URL'ингизга
# мослаб .env файлида (ёки Render Environment'да) ўрнатинг:
# WEBAPP_URL=https://sizning-app-nomi.onrender.com
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://barakabersin-bot.onrender.com")

# Эълонларни админ тасдиғисиз автомат тарзда каналга/гуруҳларга жойлаш.
# Кодлар (қўлда тасдиқлаш/рад қилиш/блоклаш) ЎЧИРИЛМАЙДИ — фақат шу флаг
# орқали четлаб ўтилади (bypass). Ёқиш учун Render Environment'да:
# AUTO_APPROVE_ADS=true
AUTO_APPROVE_ADS = os.getenv("AUTO_APPROVE_ADS", "false").strip().lower() in ("1", "true", "yes")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
