import asyncio
import logging
import sys

from aiohttp import web
from aiogram.types import (
    BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats,
    BotCommandScopeChat, BotCommandScopeDefault, MenuButtonWebApp, WebAppInfo
)
from aiogram.types.error_event import ErrorEvent
import os

from config import bot, dp, ADMINS, REVIEW_ADMINS, WEBAPP_URL
from database import init_db, seed_review_admins_from_config
from handlers import register_all_handlers
from handlers.scheduler import start_scheduler
from webapp import register_webapp_routes

# Render каби контейнерларда stdout буферланиб, логлар умуман кўринмай
# қолиши мумкин — шу сабабли line-buffering'ни мажбурий ёқамиз.
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)


@dp.errors()
async def handle_dispatcher_errors(event: ErrorEvent):
    """
    Handler ичида чиққан ҳар қандай хатоликни аниқ логга ёзади —
    аввал бундай хатолар индамай ютилиб, /start каби буйруқларга
    жавоб қайтмаслигига олиб келарди.
    """
    logging.exception(
        "Update'ни қайта ишлашда хатолик: update=%s",
        event.update,
        exc_info=event.exception,
    )
    return True


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
        commands=[
            BotCommand(command="start", description="Ботни бошлаш"),
            BotCommand(command="help", description="Йўриқнома"),
        ],
        scope=BotCommandScopeAllPrivateChats()
    )

    # ═══ ЧАТ МЕНЮ ТУГМАСИ — "Menu" ўрнига тўғридан-тўғри Mini App ═══
    # Хабар ёзиш қутиси ёнидаги стандарт "Menu" тугмаси (буйруқлар
    # рўйхатини очадиган) ўрнига, энди у бевосита эълон бериш Mini
    # App'ини очади. Гуруҳларда бу тугма умуман кўринмайди (Telegram
    # уни фақат хусусий чатларда кўрсатади), шунинг учун алоҳида
    # scope керак эмас.
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Эълон",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/adform")
        )
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
    # webapp.py'даги MAX_TOTAL_UPLOAD_BYTES (100MB) дан бироз юқори — ундан
    # катта сўровни aiohttp'нинг ўзи хотирага юкламай рад этсин. Аввалги
    # 250MB процессни (бот polling'и ҳам шу ерда) OOM'га олиб келиши мумкин эди.
    app = web.Application(client_max_size=110 * 1024 * 1024)
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

    # ═══ БОТ POLLING ═══
    # ⚠️ start_polling() ХАТОСИЗ қайтса — бу "тўхта" сигнали (SIGTERM)
    # келгани, яъни Render эски нусхани ўчираётгани дегани. Аввал бу
    # ҳолатда ҳам цикл polling'ни ҚАЙТА бошларди: эски нусха ўлмай,
    # янги деплой билан бир вақтда getUpdates сўрарди. Telegram эса
    # фақат биттасига жавоб беради (TelegramConflictError), шу сабабли
    # фойдаланувчи хабарлари "йўқолиб" қоларди.
    first_attempt = True
    while True:
        try:
            print("[*] Бот Телеграм серверига уланмоқда...")
            # Кутиб турган хабарларни фақат биринчи ишга туширишда
            # ташлаймиз — қайта уринишда фойдаланувчи хабари йўқолмасин.
            await bot.delete_webhook(drop_pending_updates=first_attempt)
            first_attempt = False
            await dp.start_polling(bot, handle_signals=True)
        except Exception as e:
            print(f"\n[!] Хатолик: {e}")
            print("[!] 15 сониядан кейин қайта уриниш...\n")
            await asyncio.sleep(15)
            continue

        # Хатосиз тугади — тўхтатиш сўралган, жараённи якунлаймиз.
        print("[*] Polling тўхтатилди — жараён якунланмоқда.")
        break

    await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Бот қўлда тўхтатилди.")
