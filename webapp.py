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

import hashlib
import hmac
import html
import json
import logging
import os
from urllib.parse import parse_qsl

from aiohttp import web
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

from config import bot, BOT_TOKEN, REVIEW_ADMINS
from database import (
    get_user_profile, save_user, get_connection, get_placeholder,
    contains_bad_word, AD_EXPIRE_DAYS, save_admin_review_message
)

routes = web.RouteTableDef()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "webapp_static")


# ═══════════════════════════════════════
# TELEGRAM initData ТЕКШИРУВИ
# ═══════════════════════════════════════

def verify_init_data(init_data: str) -> dict | None:
    """
    Telegram hujjatidagi rasmiy algoritm bo'yicha initData imzosini tekshiradi.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

    secret_key = hmac.new(key=b"WebAppData", msg=BOT_TOKEN.encode(), digestmod=hashlib.sha256).digest()
    computed_hash = hmac.new(key=secret_key, msg=data_check_string.encode(), digestmod=hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    user_raw = parsed.get("user")
    if not user_raw:
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

    profile = get_user_profile(user["id"])
    bot_info = await bot.get_me()
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
        f"#️⃣ {html.escape(fields['animal_type'])}\n"
        f"🔢 {html.escape(fields['qty'])}\n"
        f"💰 {html.escape(fields['price'])}\n"
        f"📝 {html.escape(fields['description'])}\n"
        f"📍 {html.escape(fields['region'])} в, "
        f"{html.escape(fields['district'])} т, "
        f"{html.escape(fields['mfy'])} МФЙ\n\n"
        f"📞 {html.escape(phone)}\n"
        f"👤 {html.escape(user.get('first_name') or '')} (ID: {user['id']})\n\n"
        f"🆔 Эълон ID: {ad_id}"
    )

    if not REVIEW_ADMINS:
        logging.error("REVIEW_ADMINS бўш — эълонни ҳеч ким кўра олмайди!")
        return media_meta_list

    first_admin = REVIEW_ADMINS[0]

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

            save_admin_review_message(ad_id=ad_id, admin_id=first_admin,
                                       message_id=sent.message_id, chat_id=first_admin)
        except Exception as e:
            logging.error(f"Биринчи админга ({first_admin}) юборишда хато: {e}")
    else:
        try:
            sent = await bot.send_message(
                chat_id=first_admin, text=review_text,
                parse_mode="Markdown", reply_markup=review_kb
            )
            save_admin_review_message(ad_id=ad_id, admin_id=first_admin,
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
    for admin_id in REVIEW_ADMINS[1:]:
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
            save_admin_review_message(ad_id=ad_id, admin_id=admin_id,
                                       message_id=sent.message_id, chat_id=admin_id)
        except Exception as e:
            logging.error(f"Админ {admin_id} га юборишда хато: {e}")

    return media_meta_list


# ═══════════════════════════════════════
# POST /api/ads/submit
# ═══════════════════════════════════════

@routes.post("/api/ads/submit")
async def api_submit_ad(request: web.Request):
    reader = await request.multipart()

    fields = {}
    media_files = []
    oversized_files = []

    async for part in reader:
        if part.name == "media":
            content_type = part.headers.get("Content-Type", "")
            is_video = content_type.startswith("video/")
            file_bytes = await part.read(decode=False)
            if len(file_bytes) > 20 * 1024 * 1024:  # 20 MB — Bot API limiti
                oversized_files.append(part.filename or "файл")
                continue
            media_files.append({
                "type": "video" if is_video else "photo",
                "bytes": file_bytes,
                "filename": part.filename or ("video.mp4" if is_video else "photo.jpg"),
            })
        else:
            fields[part.name] = (await part.read()).decode("utf-8")

    init_data = fields.get("initData", "")
    user = verify_init_data(init_data)
    if not user:
        return _unauthorized()

    if oversized_files:
        return web.json_response(
            {"ok": False, "error": f"Файл ҳажми жуда катта (20MB дан ошди): {', '.join(oversized_files)}"},
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
    }

    # ═══ ЁМОН СЎЗЛАРНИ ТЕКШИРИШ (ads.py билан бир хил майдонлар) ═══
    for check_field in [description, qty, price, mfy, district, phone]:
        if contains_bad_word(check_field):
            return web.json_response(
                {"ok": False, "error": "Матнда ножўя сўз аниқланди. Илтимос, тузатинг."},
                status=400
            )

    tg_username = user.get("username")
    db_username = f"@{tg_username}" if tg_username else ""

    # ═══ БАЗАГА status='pending' БИЛАН САҚЛАШ ═══
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if os.getenv("DATABASE_URL"):
            cursor.execute(f"""
                INSERT INTO ads
                (user_id, msg_id, animal_type, quantity, price,
                 price_display, description, region, district, mfy, phone, username,
                 status, expires_at)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p},
                        {p}, NOW() + INTERVAL '{AD_EXPIRE_DAYS} days')
                RETURNING id
            """, (user["id"], '', animal_type, qty, price, price,
                  description, region, district, mfy, phone, db_username, 'pending'))
        else:
            cursor.execute(f"""
                INSERT INTO ads
                (user_id, msg_id, animal_type, quantity, price,
                 price_display, description, region, district, mfy, phone, username,
                 status, expires_at)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p},
                        {p}, datetime('now', '+{AD_EXPIRE_DAYS} days'))
                RETURNING id
            """, (user["id"], '', animal_type, qty, price, price,
                  description, region, district, mfy, phone, db_username, 'pending'))

        ad_id = cursor.fetchone()[0]
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        logging.error(f"Mini App: ads INSERT хатоси: {e}")
        return web.json_response(
            {"ok": False, "error": "Базага сақлашда хатолик. Кейинроқ қайта уриниб кўринг."},
            status=500
        )
    conn.close()

    # ═══ АДМИНЛАРГА ЮБОРИШ (шу жараёнда file_id'лар олинади) ═══
    try:
        media_files = await _send_to_reviewers_webapp(ad_id, fields_clean, media_files, user, phone)
    except Exception as e:
        logging.error(f"Mini App: reviewer'larga yuborishda xato: {e}")

    # ═══ ad_media ЖАДВАЛИГА file_id'ЛАРНИ САҚЛАШ ═══
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    for media in media_files:
        if media.get("file_id"):
            cursor.execute(f"""
                INSERT INTO ad_media (ad_id, media_type, file_id)
                VALUES ({p}, {p}, {p})
            """, (ad_id, media["type"], media["file_id"]))
    conn.commit()
    conn.close()

    # ═══ ФОЙДАЛАНУВЧИГА ХАБАР (bot orqali, chunki bu HTTP so'rov, message emas) ═══
    try:
        await bot.send_message(
            chat_id=user["id"],
            text=(
                f"📩 <b>Эълонингиз қабул қилинди!</b>\n\n"
                f"Эълонингиз қисқача кўриб чиқилади.\n"
                f"Тасдиқлангандан кейин @internetmolbozor каналга автомат жойланади.\n\n"
                f"⏳ Одатда бир неча дақиқа ичида жавоб оласиз."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Фойдаланувчига хабар юборилмади: {e}")

    # ═══ ПРОФИЛНИ ЯНГИЛАШ (кейинги эълонда авто-тўлдирилсин) ═══
    save_user(
        user_id=user["id"],
        full_name=user.get("first_name"),
        username=tg_username,
        region=region,
        district=district,
        mfy=None if mfy == "Кўрсатилмаган" else mfy,
        phone=phone,
    )

    return web.json_response({"ok": True})


def register_webapp_routes(app: web.Application):
    """main.py'дан chaqiriladi — Mini App route'larini asosiy app'ga qo'shadi."""
    app.add_routes(routes)
