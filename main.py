import asyncio
import logging

from aiohttp import web
import os

from config import bot, dp
from database import init_db
from handlers import register_all_handlers
from handlers.scheduler import start_scheduler
from webapp import register_webapp_routes

logging.basicConfig(level=logging.INFO)


async def handle_render_health_check(request):
    return web.Response(text="Бот муваффақиятли ишламоқда!")


async def main_loop():
    # Маълумотлар базасини ишга тушириш (миграция ҳам шу ерда)
    init_db()

    # Барча handlerларни рўйхатдан ўтказиш
    register_all_handlers(dp)

    # Веб-сервер (Render портини банд қилиш учун + Mini App backend)
    app = web.Application(client_max_size=60 * 1024 * 1024)  # 60MB — фото/видео учун
    app.router.add_get("/", handle_render_health_check)
    register_webapp_routes(app)  # /adform, /api/profile, /api/ads/submit

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[*] Веб-сервер {port}-портда ишга тушди.")

    # ═══ SCHEDULER — фонда эслатма ва архивлаш ═══
    asyncio.create_task(start_scheduler(bot))
    print("[*] Scheduler ишга тушди.")

    # Бот polling
    while True:
        try:
            print("[*] Бот Телеграм серверига уланмоқда...")
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        except Exception as e:
            print(f"\n[!] Хатолик: {e}")
            print("[!] 15 сониядан кейин қайта уриниш...\n")
            await asyncio.sleep(15)


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Бот қўлда тўхтатилди.")
