import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = -1001419724490

# Админ ID лари — бир неча одам бўлиши mumkin
ADMINS = [72185847, 2134695872]

# Тасдиқловчи админлар (шулардан биттаси тасдиқлайди)
REVIEW_ADMINS = [72185847, 2134695872]

DATABASE_URL = os.getenv("DATABASE_URL") # PostgreSQL yoki SQLite

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
