import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = -1001419724490

# Админ ID лари — бир неча одам бўлиши mumkin
ADMINS = [72185847]

# Тасдиқловчи админлар (шулардан биттаси тасдиқлайди)
REVIEW_ADMINS = [72185847, 2134695872]

DATABASE_URL = os.getenv("DATABASE_URL") # PostgreSQL yoki SQLite

# Mini App учун асосий манзил — Render'даги сизнинг реал URL'ингизга
# мослаб .env файлида (ёки Render Environment'да) ўрнатинг:
# WEBAPP_URL=https://sizning-app-nomi.onrender.com
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.onrender.com")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
