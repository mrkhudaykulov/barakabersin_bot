"""
webapp.py

Chorva Bozor Mini App учун backend.
main.py'даги мавжуд aiohttp серверига (Render порти учун очилган)
шу файлдаги route'лар қўшилади — алоҳида сервер КЕРАК ЭМАС.

Route'лар:
  GET  /adform          — Mini App HTML саҳифасини бериш
  GET  /api/profile     — фойдаланувчи профилини қайтариш (авто-тўлдириш учун)
  POST /api/ads/submit  — эълонни қабул қилиш, "pending" ҳолатида сақлаш,
                           админларга тасдиқлаш учун юбориш

МУҲИМ: бу backend КАНАЛГА ТЎҒРИДАН-ТЎҒРИ ЖОЙЛАМАЙДИ. У фақат ads.py'даги
"➕ Эълон бериш" (FSM) оқими билан БИР ХИЛ занжирни такрорлайди:
    1. ads жадвалига status='pending' билан сақлайди
    2. ad_media жадвалига file_id'ларни сақлайди
    3. REVIEW_ADMINS'га тасдиқлаш/рад этиш тугмалари билан юборади
Қолган ҳамма нарса (каналга жойлаш, хабардорлик, блоклаш) ads.py'даги
мавжуд approve_ad_callback/reject_ad_callback орқали — ЎЗГАРИШСИЗ — ишлайди,
чунки улар фақат ads/ad_media жадвалидан ўқийди, эълон қаердан
(FSM ёки Mini App) келганини билмайди ҳам.

Хавфсизлик: ҳар бир сўров Telegram'нинг initData'сини HMAC-SHA256 орқали
текширади (Telegram hujjatidagi rasmiy algoritm).
"""

import asyncio
import hashlib
import hmac
import html
import json
import logging
import os
from urllib.parse import parse_qsl

from aiohttp import web
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

from config import bot, BOT_TOKEN
from database import (
    get_user_profile, save_user, get_connection, get_placeholder,
    contains_bad_word, parse_price_text, AD_EXPIRE_DAYS, save_admin_review_message,
    block_for_bad_words,
    validate_passport, MIN_PASSPORT_DIGITS, format_ad_id,
    get_all_review_admin_ids, is_user_blocked, is_premium_user,
    get_monthly_ad_count, MAX_ADS_PER_MONTH_REGULAR, MAX_ADS_PER_MONTH_PREMIUM
)

routes = web.RouteTableDef()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "webapp_static")

# ═══ ЮКЛАШ ЛИМИТЛАРИ ═══
# Bot API'нинг бот орқали юклаш лимити — 50MB/файл. Умумий лимит эса
# процесс хотирасини ҳимоя қилади (файллар Telegram'га юборилгунча
# хотирада турадi, бот polling'и ҳам шу процессда ишлайди).
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_MEDIA_FILES = 10               # Telegram media group'нинг макс. ҳажми
MAX_TOTAL_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_FIELD_BYTES = 64 * 1024        # оддий матн майдонлари учун етарли

# Фон вазифаларига кучли ҳавола (акс ҳолда GC уларни йўқ қилиши мумкин)
_background_tasks = set()


def _log_task_exception(task: "asyncio.Task"):
    """Фон вазифасидаги хатолик жимгина йўқолмаслиги учун."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logging.error("Mini App фон вазифасида хатолик", exc_info=exc)


# ═══════════════════════════════════════
# TELEGRAM initData ТЕКШИРУВИ
# ═══════════════════════════════════════

def verify_init_data(init_data: str) -> dict | None:
    """
    Telegram hujjatidagi rasmiy algoritm bo'yicha initData imzosini tekshiradi.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        logging.warning("[initData] БЎШ — Mini App Telegram ичида очилмаган бўлиши мумкин.")
        return None

    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError as e:
        logging.warning(f"[initData] parse_qsl хатоси: {e} | raw(120)={init_data[:120]!r}")
        return None

    logging.debug(f"[initData] Қабул қилинган калитлар: {sorted(parsed.keys())}")

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        logging.warning("[initData] 'hash' майдони йўқ!")
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

    secret_key = hmac.new(key=b"WebAppData", msg=BOT_TOKEN.encode(), digestmod=hashlib.sha256).digest()
    computed_hash = hmac.new(key=secret_key, msg=data_check_string.encode(), digestmod=hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        logging.warning("[initData] HASH МОС ЭМАС — сўров рад этилди.")
        return None

    logging.debug("[initData] ✅ Имзо тўғри тасдиқланди.")

    user_raw = parsed.get("user")
    if not user_raw:
        logging.warning("[initData] 'user' майдони йўқ!")
        return None
    try:
        return json.loads(user_raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _unauthorized():
    return web.json_response({"ok": False, "error": "Тасдиқланмади (initData нотўғри)."}, status=401)


# ═══════════════════════════════════════
# GET /adform
# ═══════════════════════════════════════

@routes.get("/adform")
async def adform_page(request: web.Request):
    path = os.path.join(STATIC_DIR, "adform.html")
    if not os.path.exists(path):
        return web.Response(text="adform.html топилмади", status=404)
    return web.FileResponse(path)


# ═══════════════════════════════════════
# GET /api/profile
# ═══════════════════════════════════════

@routes.get("/api/profile")
async def api_profile(request: web.Request):
    init_data = request.query.get("initData", "")
    user = verify_init_data(init_data)
    if not user:
        return _unauthorized()

    profile = await get_user_profile(user["id"])
    bot_info = await bot.me()
    return web.json_response({
        "ok": True,
        "profile": profile,
        "bot_username": bot_info.username,
    })


# ═══════════════════════════════════════
# АДМИНЛАРГА ЮБОРИШ (ads.py'даги _send_to_reviewers билан БИР ХИЛ формат)
# ═══════════════════════════════════════

async def _send_to_reviewers_webapp(ad_id, fields, media_meta_list, user, phone):
    """
    ads.py'даги _send_to_reviewers'нинг Mini App учун эквиваленти.
    Фарқи: медиа файллар ҳали Telegram'га юкланмаган (raw bytes) —
    биринчи админга юборишда файл юкланади ва file_id олинади,
    қолган админларга шу file_id орқали (қайта юкламасдан) юборилади.

    Қайтаради: media_meta_list'нинг ҳар бир элементига қўшилган "file_id".
    """
    review_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"approve_{ad_id}"),
            InlineKeyboardButton(text="❌ Рад қилиш", callback_data=f"reject_{ad_id}")
        ]
    ])

    review_text = (
        f"🔔 *ЯНГИ ЭЪЛОН — ТАСДИҚЛАШ КУТИЛМОҚДА*\n"
        f"_(Mini App орқали юборилди)_\n\n"
        f"{format_ad_id(ad_id)} #️⃣ {html.escape(fields['animal_type'])}\n"
        f"🔢 {html.escape(fields['qty'])}\n"
        + (f"🏷 {html.escape(fields['passport'])}\n" if fields.get('passport') else "")
        +
        f"💰 {html.escape(fields['price'])}\n"
        f"📝 {html.escape(fields['description'])}\n"
        f"📍 {html.escape(fields['region'])} в, "
        f"{html.escape(fields['district'])} т, "
        f"{html.escape(fields['mfy'])} МФЙ\n\n"
        f"📞 {html.escape(phone)}\n"
        f"👤 {html.escape(user.get('first_name') or '')} (ID: {user['id']})\n\n"
        f"🆔 Эълон ID: {ad_id}"
    )

    review_admin_ids = await get_all_review_admin_ids()
    if not review_admin_ids:
        logging.error("review_admins бўш — эълонни ҳеч ким кўра олмайди!")
        return media_meta_list

    first_admin = review_admin_ids[0]

    # ═══ 1. Биринчи медиани биринчи админга юклаб, file_id олиш ═══
    if media_meta_list:
        first_media = media_meta_list[0]
        input_file = BufferedInputFile(first_media["bytes"], filename=first_media["filename"])
        try:
            if first_media["type"] == "video":
                sent = await bot.send_video(
                    chat_id=first_admin, video=input_file,
                    caption=review_text, parse_mode="Markdown", reply_markup=review_kb
                )
                first_media["file_id"] = sent.video.file_id
            else:
                sent = await bot.send_photo(
                    chat_id=first_admin, photo=input_file,
                    caption=review_text, parse_mode="Markdown", reply_markup=review_kb
                )
                first_media["file_id"] = sent.photo[-1].file_id

            await save_admin_review_message(ad_id=ad_id, admin_id=first_admin,
                                       message_id=sent.message_id, chat_id=first_admin)
        except Exception as e:
            logging.error(f"Биринчи админга ({first_admin}) юборишда хато: {e}")
    else:
        try:
            sent = await bot.send_message(
                chat_id=first_admin, text=review_text,
                parse_mode="Markdown", reply_markup=review_kb
            )
            await save_admin_review_message(ad_id=ad_id, admin_id=first_admin,
                                       message_id=sent.message_id, chat_id=first_admin)
        except Exception as e:
            logging.error(f"Биринчи админга ({first_admin}) юборишда хато: {e}")

    # ═══ 2. Қолган медиаларнинг file_id'сини олиш (жимгина юклаб, ўчириб қўямиз) ═══
    for media in media_meta_list[1:]:
        input_file = BufferedInputFile(media["bytes"], filename=media["filename"])
        try:
            if media["type"] == "video":
                tmp = await bot.send_video(chat_id=first_admin, video=input_file)
                media["file_id"] = tmp.video.file_id
            else:
                tmp = await bot.send_photo(chat_id=first_admin, photo=input_file)
                media["file_id"] = tmp.photo[-1].file_id
            await bot.delete_message(chat_id=first_admin, message_id=tmp.message_id)
        except Exception as e:
            logging.error(f"Қўшимча медиа file_id олишда хато: {e}")

    # ═══ 3. Қолган REVIEW_ADMINS'га (агар бир нечта бўлса) file_id орқали юбориш ═══
    for admin_id in review_admin_ids[1:]:
        try:
            if media_meta_list and media_meta_list[0].get("file_id"):
                first_media = media_meta_list[0]
                if first_media["type"] == "video":
                    sent = await bot.send_video(
                        chat_id=admin_id, video=first_media["file_id"],
                        caption=review_text, parse_mode="Markdown", reply_markup=review_kb
                    )
                else:
                    sent = await bot.send_photo(
                        chat_id=admin_id, photo=first_media["file_id"],
                        caption=review_text, parse_mode="Markdown", reply_markup=review_kb
                    )
            else:
                sent = await bot.send_message(
                    chat_id=admin_id, text=review_text,
                    parse_mode="Markdown", reply_markup=review_kb
                )
            await save_admin_review_message(ad_id=ad_id, admin_id=admin_id,
                                       message_id=sent.message_id, chat_id=admin_id)
        except Exception as e:
            logging.error(f"Админ {admin_id} га юборишда хато: {e}")

    return media_meta_list


# ═══════════════════════════════════════
# POST /api/ads/submit
# ═══════════════════════════════════════

@routes.post("/api/ads/submit")
async def api_submit_ad(request: web.Request):
    try:
        return await _api_submit_ad_inner(request)
    except Exception:
        # Кутилмаган ҳар қандай хатолик — хом aiohttp 500 (ва ичкаридаги
        # техник тафсилотлар) ўрниға тоза JSON жавоб қайтарамиз.
        logging.exception("Mini App: /api/ads/submit'да кутилмаган хатолик")
        return web.json_response(
            {"ok": False, "error": "Сервер хатоси. Кейинроқ қайта уриниб кўринг."},
            status=500
        )


async def _read_part_limited(part, max_bytes: int):
    """
    Multipart қисмини бўлак-бўлак ўқийди ва лимитдан ошиши билан
    ўқишни тўхтатади — бутун файлни хотирага юклаб, кейин "катта экан"
    деб ташлаб юбормаслик учун (акс ҳолда бу DoS йўли бўларди).
    Қайтаради: (bytes ёки None, лимитдан ошдими).
    """
    chunks = []
    size = 0
    while True:
        chunk = await part.read_chunk()
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            # Қолган қисмини хотирага йиғмасдан ўқиб тугатамиз
            while await part.read_chunk():
                pass
            return None, True
        chunks.append(chunk)
    return b"".join(chunks), False


async def _api_submit_ad_inner(request: web.Request):
    reader = await request.multipart()

    fields = {}
    media_files = []
    oversized_files = []
    total_media_bytes = 0
    user = None

    async for part in reader:
        if part.name == "media":
            # ⚠️ Медиани ФАҚАТ имзо текширилгандан кейин хотирага ўқиймиз.
            # Mini App формаси initData'ни файллардан олдин юборади, шунинг
            # учун аутентификациясиз сўров бу ерга умуман етиб келмайди —
            # бегона клиент юзлаб мегабайтни серверга буферлата олмайди.
            if user is None:
                return _unauthorized()

            if len(media_files) + len(oversized_files) >= MAX_MEDIA_FILES:
                return web.json_response(
                    {"ok": False, "error": f"Файллар сони кўп (максимум {MAX_MEDIA_FILES} та)."},
                    status=400
                )

            content_type = part.headers.get("Content-Type", "")
            is_video = content_type.startswith("video/")
            file_bytes, too_big = await _read_part_limited(part, MAX_FILE_BYTES)
            if too_big:
                oversized_files.append(part.filename or "файл")
                continue

            total_media_bytes += len(file_bytes)
            if total_media_bytes > MAX_TOTAL_UPLOAD_BYTES:
                return web.json_response(
                    {"ok": False, "error": "Юкланган файллар умумий ҳажми жуда катта."},
                    status=413
                )

            media_files.append({
                "type": "video" if is_video else "photo",
                "bytes": file_bytes,
                "filename": part.filename or ("video.mp4" if is_video else "photo.jpg"),
            })
        else:
            raw, too_big = await _read_part_limited(part, MAX_FIELD_BYTES)
            if too_big:
                return web.json_response(
                    {"ok": False, "error": "Матн майдони жуда узун."}, status=400
                )
            try:
                value = raw.decode("utf-8")
            except UnicodeDecodeError:
                return web.json_response(
                    {"ok": False, "error": "Маълумот форматида хатолик."}, status=400
                )
            fields[part.name] = value

            if part.name == "initData":
                user = verify_init_data(value)
                if not user:
                    return _unauthorized()

    if user is None:
        return _unauthorized()

    if await is_user_blocked(user["id"]):
        return web.json_response(
            {"ok": False, "error": "Сиз блоклангансиз. Эълон бериш ҳуқуқингиз чекланган."},
            status=403
        )

    is_premium = await is_premium_user(user["id"])
    limit = MAX_ADS_PER_MONTH_PREMIUM if is_premium else MAX_ADS_PER_MONTH_REGULAR
    monthly_count = await get_monthly_ad_count(user["id"])
    if monthly_count >= limit:
        return web.json_response(
            {"ok": False, "error": f"Ойлик лимит тугади ({monthly_count}/{limit})."},
            status=403
        )

    if oversized_files:
        return web.json_response(
            {"ok": False, "error": f"Файл ҳажми жуда катта (50MB дан ошди): {', '.join(oversized_files)}"},
            status=400
        )

    required = ["animal_type", "region", "district", "qty", "price", "phone"]
    missing = [f for f in required if not fields.get(f, "").strip()]
    if missing:
        return web.json_response(
            {"ok": False, "error": f"Тўлдирилмаган майдонлар: {', '.join(missing)}"},
            status=400
        )
    if not media_files:
        return web.json_response(
            {"ok": False, "error": "Камида битта расм ёки видео юкланг."},
            status=400
        )

    # Паспорт рақами ИХТИЁРИЙ — бўш бўлса эълон рақамсиз кетаверади.
    # Аммо ниманидир ёзилган бўлса, у бот оқимидаги билан БИР ХИЛ
    # қоидадан (database.validate_passport) ўтиши керак.
    passport_raw = fields.get("passport", "").strip()
    passport = validate_passport(passport_raw) if passport_raw else None
    if passport_raw and not passport:
        return web.json_response(
            {"ok": False,
             "error": f"Ҳайвон паспорти рақами тўғри эмас "
                      f"(камида {MIN_PASSPORT_DIGITS} та рақам бўлиши керак). "
                      f"Ёки уни бўш қолдиринг."},
            status=400
        )

    animal_type = fields["animal_type"].strip()
    region = fields["region"].strip()
    district = fields["district"].strip()
    mfy = fields.get("mfy", "").strip() or "Кўрсатилмаган"
    qty = fields["qty"].strip()
    price = fields["price"].strip()
    description = fields.get("description", "").strip() or "Киритилмаган"
    phone = fields["phone"].strip()

    fields_clean = {
        "animal_type": animal_type, "region": region, "district": district,
        "mfy": mfy, "qty": qty, "price": price, "description": description,
        "passport": passport,
    }

    # ═══ ЁМОН СЎЗЛАРНИ ТЕКШИРИШ (ads.py билан бир хил майдонлар) ═══
    # ⚠️ Аввал бу ерда эълон фақат рад этиларди — энди бот оқимидаги
    # каби биринчи уринишдаёқ дарҳол блокланади (block_for_bad_words).
    for check_field in [description, qty, price, mfy, district, phone, passport or ""]:
        if contains_bad_word(check_field):
            await block_for_bad_words(user["id"])
            return web.json_response(
                {"ok": False,
                 "error": "🚫 Сиз блокландингиз! Матнда ножўя сўз аниқланди."},
                status=403
            )

    tg_username = user.get("username")
    db_username = f"@{tg_username}" if tg_username else ""

    # ═══ БАЗАГА status='pending' БИЛАН САҚЛАШ ═══
    def _insert_pending_ad_sync():
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if os.getenv("DATABASE_URL"):
                cursor.execute(f"""
                    INSERT INTO ads
                    (user_id, msg_id, animal_type, quantity, price, price_num,
                     price_display, passport, description, region, district, mfy, phone, username,
                     status, expires_at)
                    VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p},
                            {p}, {p}, NOW() + INTERVAL '{AD_EXPIRE_DAYS} days')
                    RETURNING id
                """, (user["id"], '', animal_type, qty, price,
                      int(parse_price_text(price) or 0), price, passport,
                      description, region, district, mfy, phone, db_username, 'pending'))
            else:
                cursor.execute(f"""
                    INSERT INTO ads
                    (user_id, msg_id, animal_type, quantity, price, price_num,
                     price_display, passport, description, region, district, mfy, phone, username,
                     status, expires_at)
                    VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p},
                            {p}, {p}, datetime('now', '+{AD_EXPIRE_DAYS} days'))
                    RETURNING id
                """, (user["id"], '', animal_type, qty, price,
                      int(parse_price_text(price) or 0), price, passport,
                      description, region, district, mfy, phone, db_username, 'pending'))

            new_ad_id = cursor.fetchone()[0]
            conn.commit()
            return new_ad_id
        except Exception as e:
            conn.rollback()
            logging.error(f"Mini App: ads INSERT хатоси: {e}")
            return None
        finally:
            conn.close()

    ad_id = await asyncio.to_thread(_insert_pending_ad_sync)
    if ad_id is None:
        return web.json_response(
            {"ok": False, "error": "Базага сақлашда хатолик. Кейинроқ қайта уриниб кўринг."},
            status=500
        )

    # ═══ ФОЙДАЛАНУВЧИГА ДАРҲОЛ ЖАВОБ (kutish kerak bo'lmasin) ═══
    # Қолган БАРЧА секин иш (reviewer/guruhларга юбориш, ad_media, профиль,
    # фойдаланувчига хабар) — фон режимида, HTTP javobidan KEYIN davom etadi.
    task = asyncio.create_task(
        _process_ad_after_insert(
            ad_id=ad_id,
            fields_clean=fields_clean,
            media_files=media_files,
            user=user,
            phone=phone,
            tg_username=tg_username,
            animal_type=animal_type,
            qty=qty,
            price=price,
            description=description,
            region=region,
            district=district,
            mfy=mfy,
        )
    )
    # Фон вазифасига ҳавола сақланмаса, GC уни ярим йўлда тўхтатиши мумкин;
    # хатолиги ҳам ҳеч ким ўқимаган "Task exception was never retrieved"
    # бўлиб қолар эди. Шунинг учун ҳаволани ушлаб турамиз ва хатони логга
    # ёзамиз.
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    task.add_done_callback(_log_task_exception)

    return web.json_response({"ok": True})


async def _process_ad_after_insert(
    ad_id, fields_clean, media_files, user, phone, tg_username,
    animal_type, qty, price, description, region, district, mfy
):
    """
    Эълон базага сақлангандан КЕЙИН бажариладиган, СЕКИН қисм —
    фон режимида (background task) ишлайди, HTTP жавобини кутиб турмайди.
    Фойдаланувчи Mini App'да дарҳол "қабул қилинди" кўради, шу орада
    бу функция реал ишни (юклаш, юбориш) орқа фонда давом эттиради.
    """
    # ═══ АДМИНЛАРГА ЮБОРИШ (шу жараёнда file_id'лар олинади) ═══
    try:
        media_files = await _send_to_reviewers_webapp(ad_id, fields_clean, media_files, user, phone)
    except Exception as e:
        logging.error(f"Mini App: reviewer'larga yuborishda xato: {e}")
    # ДИҚҚАТ: Гуруҳларга ЭНДИ фақат тасдиқлангандан кейин, markazlashgan
    # review_admins tomonidan (ads.py'даги approve_ad_callback ичида) юборилади.

    # ═══ ad_media ЖАДВАЛИГА file_id'ЛАРНИ САҚЛАШ ═══
    def _save_ad_media_sync():
        p = get_placeholder()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            for media in media_files:
                if media.get("file_id"):
                    cursor.execute(f"""
                        INSERT INTO ad_media (ad_id, media_type, file_id)
                        VALUES ({p}, {p}, {p})
                    """, (ad_id, media["type"], media["file_id"]))
            conn.commit()
        finally:
            conn.close()

    try:
        await asyncio.to_thread(_save_ad_media_sync)
    except Exception:
        logging.exception(f"Mini App: ad_media сақлашда хатолик (ad_id={ad_id})")

    # ═══ ФОЙДАЛАНУВЧИГА ХАБАР (bot orqali, chunki bu HTTP so'rov, message emas) ═══
    try:
        await bot.send_message(
            chat_id=user["id"],
            text=(
                f"📩 <b>Эълонингиз қабул қилинди!</b>\n\n"
                f"Эълонингиз қисқача кўриб чиқилади.\n"
                f"Тасдиқлангандан кейин @internetmolbozor каналга, шунингдек "
                f"тегишли вилоят гуруҳ(лар)ига автомат жойланади.\n\n"
                f"⏳ Одатда бир неча дақиқа ичида жавоб оласиз."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Фойдаланувчига хабар юборилмади: {e}")

    # ═══ ПРОФИЛНИ ЯНГИЛАШ (кейинги эълонда авто-тўлдирилсин) ═══
    await save_user(
        user_id=user["id"],
        full_name=user.get("first_name"),
        username=tg_username,
        region=region,
        district=district,
        mfy=None if mfy == "Кўрсатилмаган" else mfy,
        phone=phone,
    )


def register_webapp_routes(app: web.Application):
    """main.py'дан chaqiriladi — Mini App route'larini asosiy app'ga qo'shadi."""
    app.add_routes(routes)
