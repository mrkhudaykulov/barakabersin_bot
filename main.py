import asyncio
import logging

from aiohttp import web
from aiogram.types import (
    BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats,
    BotCommandScopeChat, BotCommandScopeDefault
)
import os

from config import bot, dp, ADMINS, REVIEW_ADMINS
from database import init_db, seed_review_admins_from_config
from handlers import register_all_handlers
from handlers.scheduler import start_scheduler
from webapp import register_webapp_routes

logging.basicConfig(level=logging.INFO)


async def handle_render_health_check(request):
    return web.Response(text="Бот муваффақиятли ишламоқда!")


async def setup_bot_commands():
    """
    "/" менюси — ҲАММАГА (админ ҳам, оддий фойдаланувчи ҳам) приват чатда
    фақат /start кўринади. Қолган буйруқлар (vetadmin, reviewadmins,
    clearprices_confirm, viloyat va h.k.) пастдаги клавиатура тугмалари
    орқали аллақачон мавjud — "/" менюсида кўрсатишга ҳожат йўқ.
    Гуруҳларда — ҳеч қандай буйруқ кўринмайди.
    """
    # Аввал БАРЧА scope'ларни тозалаймиз — олдинги деплойда бош админга
    # BotCommandScopeChat орқали ўрнатилган тўлиқ рўйхат бўлса, у энг юқори
    # устуворликка эга бўлгани учун очиқ равишда ўчирилмаса, қолиб кетади.
    await bot.delete_my_commands(scope=BotCommandScopeDefault())
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    for admin_id in ADMINS:
        try:
            await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logging.warning(f"Админ {admin_id} учун эски буйруқлар тозаланмади: {e}")

    await bot.set_my_commands(
        commands=[BotCommand(command="start", description="Ботни бошлаш")],
        scope=BotCommandScopeAllPrivateChats()
    )


async def main_loop():
    # Маълумотлар базасини ишга тушириш (миграция ҳам шу ерда)
    await init_db()

    # config.py'даги REVIEW_ADMINS'ни DB'даги яxлит review_admins
    # ҳавзасига boshlang'ich sifatida qo'shib qo'yamiz (takrorlanmaydi)
    await seed_review_admins_from_config(set(ADMINS) | set(REVIEW_ADMINS))

    # Барча handlerларни рўйхатдан ўтказиш
    register_all_handlers(dp)

    # "/" менюсини чат турига қараб тўғрилаш
    await setup_bot_commands()

    # Веб-сервер (Render портини банд қилиш учун + Mini App backend)
    app = web.Application(client_max_size=250 * 1024 * 1024)  # 250MB — бир нечта 50MB'лик видео учун жой
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
