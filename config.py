import os
from aiogram import Bot, Dispatcher

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = -1001419724490
ADMINS = [72185847, 2134695872]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
