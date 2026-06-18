import html
import logging

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaVideo
)

from config import bot, CHANNEL_ID
from states import AdStates
from keyboards import (
    main_menu, cancel_keyboard, photo_confirm_keyboard,
    animal_types_keyboard, regions_keyboard, districts_keyboard,
    standard_step_keyboard, description_keyboard, phone_keyboard
)
from database import (
    contains_bad_word, parse_price_text, 
    MIN_PRICE, MAX_PRICE,
    fmt_number, fix_keyboard_text,
    get_connection, get_placeholder,
    save_user, get_user_phone, 
    repost_ad, is_premium_user, 
    archive_ad, AD_EXPIRE_DAYS,
    get_notification_users, is_user_blocked, 
    approve_ad, reject_ad,
    get_pending_ad, increment_rejection, 
    MAX_REJECTIONS, save_admin_review_message, 
    get_admin_review_messages, delete_admin_review_messages,
    get_monthly_ad_count,
    MAX_ADS_PER_MONTH_REGULAR,
    MAX_ADS_PER_MONTH_PREMIUM
)

router = Router()


# ═══════════════════════════════════════
# ➕ ЭЪЛОН БЕРИШ
# ═══════════════════════════════════════

@router.message(F.text == "➕ Эълон бериш")
async def start_ad(message: types.Message, state: FSMContext):
    # ═══ БЛОК ТЕКШИРИШ ═══
    if is_user_blocked(message.from_user.id):
        await message.answer(
            "🚫 *Сиз блоклангансиз!*\n\n"
            "Эълон бериш ҳуқуқингиз чекланган.\n"
            "Сабаб: Эълонларингиз бир неча марта "
            "админ томонидан рад этилган.\n\n",            
            parse_mode="Markdown"
        )
        return
    
    await state.clear()

    # ═══ ОЙЛИК ЛИМИТ ТЕКШИРИШ ═══
    user_id = message.from_user.id
    is_premium = is_premium_user(user_id)
    limit = MAX_ADS_PER_MONTH_PREMIUM if is_premium else MAX_ADS_PER_MONTH_REGULAR

    monthly_count = get_monthly_ad_count(user_id)

    if monthly_count >= limit:
        status_text = "Премиум" if is_premium else "оддий"
        await message.answer(
            f"⚠️ *Ойлик лимит тугади!*\n\n"
            f"👤 Сиз {status_text} фойдаланувчисиз\n"
            f"📊 Бу ойда: *{monthly_count}/{limit}* та эълон жойланди\n\n"            
            f"Кейинги ойда қайта фойдаланишингиз мумкин.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        return

    await state.clear()
    
    # Фойдаланувчини базага сақлаш (тез рўйхатга олиш)
    save_user(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username
    )

    remaining = limit - monthly_count - 1
    await state.set_state(AdStates.photo)
    await state.update_data(media_list=[])
    await message.answer(
        f"Илтимос, ҳайвоннинг расмларини ёки видеосини юборинг "
        f"(Бир нечта юборишингиз мумкин).\n\n"
        f"📊 Ойлик лимит: *{monthly_count + 1}/{limit}* "
        f"(қолди: {remaining} та)\n\n"
        f"Юбориб бўлгач '📥 Расмларни тасдиқлаш' тугмасини босинг:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )   


@router.message(AdStates.photo, F.photo | F.video)
async def process_photo(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    media_list = user_data.get("media_list", [])

    if message.video:
        media_list = [m for m in media_list if m["type"] == "video"]
        if len(media_list) >= 4:
            await message.answer(
                "⚠️ Максимум 4 та видео юбориш мумкин.\n"
                "Тасдиқлаш тугмасини босинг:",
                reply_markup=photo_confirm_keyboard()
            )
            return
        media_list.append({"type": "video", "file_id": message.video.file_id})
        await state.update_data(media_list=media_list)
        await message.answer(
            f"🎥 {len(media_list)}-видео қабул қилинди.\n"
            f"{'_Фотолар ўчирилди — фақат видео сақланади._' + chr(10) if any(m['type'] == 'photo' for m in user_data.get('media_list', [])) else ''}"
            f"Яна юборишингиз мумкин (макс: 4 та). Тугатсангиз, пастки тугмани босинг:",
            parse_mode="Markdown",
            reply_markup=photo_confirm_keyboard()
        )
    elif message.photo:
        if any(m["type"] == "video" for m in media_list):
            await message.answer(
                "⚠️ Видео аллақачон юборилган.\n"
                "Фото ва видеони аралаштириб бўлмайди.\n\n"
                "Фақат видео юборинг ёки тасдиқлаш тугмасини босинг:",
                reply_markup=photo_confirm_keyboard()
            )
            return
        if len(media_list) >= 5:
            await message.answer(
                "⚠️ Максимум 5 та расм юбориш мумкин.\n"
                "Тасдиқлаш тугмасини босинг:",
                reply_markup=photo_confirm_keyboard()
            )
            return
        media_list.append({"type": "photo", "file_id": message.photo[-1].file_id})
        await state.update_data(media_list=media_list)
        await message.answer(
            f"✅ {len(media_list)}-расм қабул қилинди. "
            f"Яна юборишингиз мумкин (макс: 5 та). Тугатсангиз, пастки тугмани босинг:",
            reply_markup=photo_confirm_keyboard()
        )

@router.message(AdStates.photo, F.text == "📥 Расмларни тасдиқлаш")
async def confirm_photos(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    media_list = user_data.get("media_list", [])
    if not media_list:
        await message.answer("⚠️ Илтимос, камида 1 та расм юборинг.")
        return
    await state.set_state(AdStates.animal_type)
    await message.answer(
        "Ҳайвон турини танланг:",
        reply_markup=animal_types_keyboard()
    )


@router.message(AdStates.photo)
async def process_photo_invalid(message: types.Message, state: FSMContext):
    if message.text == "❌ Бекор қилиш":
        await state.clear()
        await message.answer("❌ Жараён бекор қилинди.", reply_markup=main_menu())
        return
    if message.text == "🔙 Орқага":
        await message.answer(
            "📸 Расм юборинг ёки бекор қилинг.",
            reply_markup=cancel_keyboard()
        )
        return
    await message.answer(
        "⚠️ Илтимос, фақат расм ёки видео юборинг ва "
        "'📥 Расмларни тасдиқлаш' тугмасини босинг."
    )


@router.message(AdStates.animal_type)
async def process_type(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    fixed = fix_keyboard_text(message.text)
    await state.update_data(animal_type=fixed)
    await state.set_state(AdStates.region)
    await message.answer("Вилоятни танланг:", reply_markup=regions_keyboard())


@router.message(AdStates.region)
async def process_region(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    fixed = fix_keyboard_text(message.text)
    await state.update_data(region=fixed)
    await state.set_state(AdStates.district)
    await message.answer(
        "Туманни танланг:",
        reply_markup=districts_keyboard(message.text)
    )


@router.message(AdStates.district)
async def process_district(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    fixed = fix_keyboard_text(message.text)
    await state.update_data(district=fixed)
    await state.set_state(AdStates.mfy)
    await message.answer(
        "МФЙ номини ёзинг (матн кўринишида):",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdStates.mfy)
async def process_mfy(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    await state.update_data(mfy=message.text)
    await state.set_state(AdStates.quantity)
    await message.answer(
        "Сонини киритинг (масалан: 2 бош, 5 та):",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdStates.quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    if not any(char.isdigit() for char in message.text):
        await message.answer(
            "⚠️ Илтимос, сонини рақамларда кўрсатинг (масалан: 2 бош ёки 5 та):",
            reply_markup=standard_step_keyboard()
        )
        return
    await state.update_data(quantity=message.text)
    await state.set_state(AdStates.price)
    await message.answer(
        "Нархини киритинг (масалан: 15 000 000 сўм):",
        reply_markup=standard_step_keyboard()
    )


@router.message(AdStates.price)
async def process_price(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    if not any(char.isdigit() for char in message.text):
        await message.answer(
            "⚠️ Илтимос, нархни рақамларда киритинг (масалан: 12 000 000 сўм):",
            reply_markup=standard_step_keyboard()
        )
        return

    price_value = parse_price_text(message.text)

    if price_value == 0:
        await message.answer(
            "⚠️ Нарх топилмади. Илтимос, рақамда ёзинг:\n"
            "Масалан: `15000000` ёки `15 млн` ёки `15000 минг`",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
        return

    if price_value < MIN_PRICE:
        await message.answer(
            f"⚠️ Нарх жуда кичик!\n\n"
            f"Камида *{fmt_number(MIN_PRICE)} сўм* бўлгани маъқул.\n"
            f"Қайтадан киритинг:",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
        return

    if price_value > MAX_PRICE:
        await message.answer(
            f"⚠️ Нарх жуда катта!\n\n"
            f"Энг кўпи *{fmt_number(MAX_PRICE)} сўм* бўлиши мумкин.\n"
            f"Агар нарх тўғри бўлса, қисмларда ёзинг ёки "
            f"админ билан боғланинг.\n\n"
            f"Қайтадан киритинг:",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
        return

    await state.update_data(price=message.text)
    await state.set_state(AdStates.description)
    await message.answer(
        "Қўшимча изоҳ қолдирасизми? Агар зарур бўлмаса, пастки тугмани босинг:",
        reply_markup=description_keyboard()
    )


@router.message(AdStates.description)
async def process_description(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    if message.text == "⏭ Ёзмасдан ўтказиб юбориш":
        await state.update_data(description="Киритилмаган")
    else:
        # ═══ УЗУНЛИК ТЕКШИРИШ ═══
        desc = message.text[:300]  # 300 белгига чеклаш
        if len(message.text) > 300:
            await message.answer(
                f"⚠️ Изоҳ жуда узун ({len(message.text)} белги). "
                f"Узр 300 та белгидан ошиш мумкин эмас.\n\n"                
            )
        await state.update_data(description=desc)            

    # ═══ ТЕЗ РЎЙХАТГА ОЛИШ: базада телефон борми? ═══
    saved_phone = get_user_phone(message.from_user.id)
    if saved_phone:
        await state.update_data(saved_phone=saved_phone)
        # Сақланган телефонни кўрсатиб, тасдиқ сўраймиз
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"✅ Ҳа, {saved_phone}",
                callback_data="use_saved_phone"
            ),
            InlineKeyboardButton(
                text="📱 Янги рақам",
                callback_data="new_phone"
            )
        ]])
        await message.answer(
            f"📞 Аввалги рақамингиз: <b>{saved_phone}</b>\n\n"
            f"Шу рақамдан фойдаланасизми?",
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        await state.set_state(AdStates.phone)
        await message.answer(
            "Алоқа учун телефон рақамингизни юборинг:\n"
            "⚠️ Диққат! Сизга харидорлар шу рақам орқали телефон қилиши учун, "
            "ТЕЛЕФОН рақамингиз ва фойдаланувчи номи эълонда кўринади!",
            reply_markup=phone_keyboard()
        )


@router.callback_query(F.data == "use_saved_phone")
async def use_saved_phone(callback: types.CallbackQuery, state: FSMContext):
    """Сақланган телефонни ишлатиш"""
    data = await state.get_data()
    phone = data.get("saved_phone")
    await callback.message.delete()
    await _finalize_ad(callback.message, state, phone, callback.from_user)
    await callback.answer()


@router.callback_query(F.data == "new_phone")
async def request_new_phone(callback: types.CallbackQuery, state: FSMContext):
    """Янги телефон рақами сўраш"""
    await callback.message.delete()
    await state.set_state(AdStates.phone)
    await callback.message.answer(
        "📱 Янги телефон рақамингизни юборинг:",
        reply_markup=phone_keyboard()
    )
    await callback.answer()


@router.message(AdStates.phone, F.contact | F.text)
async def process_phone(message: types.Message, state: FSMContext):
    if message.text and not any(char.isdigit() for char in message.text):
        await message.answer(
            "⚠️ Илтимос, телефон рақамни тўғри форматда ёзинг.",
            reply_markup=phone_keyboard()
        )
        return

    phone = message.contact.phone_number if message.contact else message.text

    # Телефонни базага сақлаш (кейинги эълонда тез рўйхатга олиш учун)
    save_user(
        user_id=message.from_user.id,
        phone=phone
    )

    await _finalize_ad(message, state, phone, message.from_user)


# Якуний эълон бериш жараёни

async def _finalize_ad(message: types.Message, state: FSMContext, phone: str, user):
    """
    Эълонни базага сақлаш (pending) ва админларга юбориш.
    process_phone ва use_saved_phone иккаласидан чақирилади.
    """
    data = await state.get_data()

    # ═══ ЁМОН СЎЗЛАРНИ ТЕКШИРИШ ═══
    check_fields = [
        data.get('description', ''),
        data.get('quantity', ''),
        data.get('price', ''),
        data.get('mfy', ''),
        data.get('district', ''),
        phone,
    ]

    for field in check_fields:
        if contains_bad_word(field):
            await message.answer(
                "🚫 *Эълонингизда ножўя матн аниқланди!*\n\n"
                "Илтимос, тоза матн билан ёзинг.\n"
                "Ҳайвон сотиш бўлимида илтимос одобли бўлинг.",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
            await state.clear()
            return

    if user.username:
        username_text = f"@{user.username}"
    else:
        username_text = (
            f"<a href='tg://user?id={user.id}'>"
            f"{user.full_name}</a> (Ник йўқ)"
        )

    bot_info = await bot.get_me()
    caption = (
        f"#️⃣ #{html.escape(data['animal_type'])}\n"
        f"🔢 <b>Сони:</b> {html.escape(data['quantity'])}\n"
        f"💰 <b>Нархи:</b> {html.escape(data['price'])}\n"
        f"📝 <b>Изоҳ:</b> {html.escape(data['description'])}\n"
        f"📍 <b>Манзил:</b> {html.escape(data['region'])} в, "
        f"{html.escape(data['district'])} т, "
        f"{html.escape(data['mfy'])} МФЙ\n\n"
        f"📞 <b>Алоқа:</b> {html.escape(phone)}\n"
        f"💬 <b>Телеграм:</b> {username_text}\n\n"
        f"Канал: @internetmolbozor\n"
        f"Эълон жойланг: @{bot_info.username}"
    )

    media_list = data.get("media_list", [])

    try:
        db_username = (
            f"@{user.username}"
            if user.username
            else f"ID: {user.id}"
        )

        # ═══ БАЗАГА САҚЛАШ — status = 'pending' ═══
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()

        if __import__('os').getenv("DATABASE_URL"):
            cursor.execute(f"""
                INSERT INTO ads
                (user_id, msg_id, animal_type, quantity, price,
                 description, region, district, mfy, phone, username,
                 status, expires_at)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p},
                        {p}, NOW() + INTERVAL '{AD_EXPIRE_DAYS} days')
                RETURNING id
            """, (
                user.id, '',
                data['animal_type'], data['quantity'], data['price'],
                data['description'], data['region'], data['district'],
                data['mfy'], phone, db_username, 'pending'
            ))
        else:
            cursor.execute(f"""
                INSERT INTO ads
                (user_id, msg_id, animal_type, quantity, price,
                 description, region, district, mfy, phone, username,
                 status, expires_at)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p},
                        {p}, datetime('now', '+{AD_EXPIRE_DAYS} days'))
                RETURNING id
            """, (
                user.id, '',
                data['animal_type'], data['quantity'], data['price'],
                data['description'], data['region'], data['district'],
                data['mfy'], phone, db_username, 'pending'
            ))

        ad_id = cursor.fetchone()[0]
        # ═══ МЕДИАЛАРНИ ad_media ЖАДВАЛИГА САҚЛАШ
        if media_list and ad_id:
            for media in media_list:
                cursor.execute(f"""
                    INSERT INTO ad_media (ad_id, media_type, file_id)
                    VALUES ({p}, {p}, {p})
                """, (ad_id, media.get('type'), media.get('file_id')))
                
        conn.commit()
        conn.close()

        # ═══ ФОЙДАЛАНУВЧИГА ХАБАР ═══
        await message.answer(
            f"📩 *Эълонингиз қабул қилинди!*\n\n"
            f"Эълонингиз қисқача кўриб чиқилади.\n"
            f"Тасдиқлангандан кейин автомат каналга жойланади.\n\n"
            f"⏳ Одатда бир неча дақиқа ичида жавоб оласиз.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

        # ═══ АДМИНЛАРГА ЮБОРИШ ═══
        await _send_to_reviewers(
            ad_id=ad_id,
            data=data,
            caption=caption,
            media_list=media_list,
            user=user,
            phone=phone
        )

    except Exception as e:
        logging.error(f"Эълон жойлашда хато: {e}")
        await message.answer(
            f"Хатолик юз берди: {e}",
            reply_markup=main_menu()
        )

    await state.clear()


# ═══════════════════════════════════════
# АДМИНЛАРГА ЮБОРИШ
# ═══════════════════════════════════════


async def _send_to_reviewers(ad_id, data, caption, media_list, user, phone):
    """Эълонни барча админларга тасдиқлаш учун юбориш ва хабар ID ларини сақлаш."""
    from config import REVIEW_ADMINS
 
    review_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Тасдиқлаш", callback_data=f"approve_{ad_id}"),
            InlineKeyboardButton(text="❌ Рад қилиш", callback_data=f"reject_{ad_id}")
        ]
    ])
 
    review_text = (
        f"🔔 *ЯНГИ ЭЪЛОН — ТАСДИҚЛАШ КУТИЛМОQДА*\n\n"
        f"#️⃣ {html.escape(data['animal_type'])}\n"
        f"🔢 {html.escape(data['quantity'])}\n"
        f"💰 {html.escape(data['price'])}\n"
        f"📝 {html.escape(data['description'])}\n"
        f"📍 {html.escape(data['region'])} в, "
        f"{html.escape(data['district'])} т, "
        f"{html.escape(data['mfy'])} МФЙ\n\n"
        f"📞 {html.escape(phone)}\n"
        f"👤 {user.full_name} (ID: {user.id})\n\n"
        f"🆔 Эълон ID: {ad_id}"
    )
 
    for admin_id in REVIEW_ADMINS:
        try:
            if media_list:
                first_media = media_list[0]
                if first_media["type"] == "photo":
                    sent = await bot.send_photo(
                        chat_id=admin_id,
                        photo=first_media["file_id"],
                        caption=review_text,
                        parse_mode="Markdown",
                        reply_markup=review_kb
                    )
                elif first_media["type"] == "video":
                    sent = await bot.send_video(
                        chat_id=admin_id,
                        video=first_media["file_id"],
                        caption=review_text,
                        parse_mode="Markdown",
                        reply_markup=review_kb
                    )
                else:
                    sent = await bot.send_message(
                        chat_id=admin_id,
                        text=review_text,
                        parse_mode="Markdown",
                        reply_markup=review_kb
                    )
            else:
                sent = await bot.send_message(
                    chat_id=admin_id,
                    text=review_text,
                    parse_mode="Markdown",
                    reply_markup=review_kb
                )
 
            # ═══ Хабар ID сини базага сақлаш ═══
            save_admin_review_message(
                ad_id=ad_id,
                admin_id=admin_id,
                message_id=sent.message_id,
                chat_id=admin_id
            )
 
        except Exception as e:
            logging.error(f"Админ {admin_id} га юборишда хато: {e}")
 

# ═══════════════════════════════════════
# ТАСДИҚЛАШ КАЛЛБЕК
# ═══════════════════════════════════════

@router.callback_query(F.data.startswith("approve_"))
async def approve_ad_callback(callback: types.CallbackQuery):
    from config import REVIEW_ADMINS

    if callback.from_user.id not in REVIEW_ADMINS:
        await callback.answer("⛔ Сиз админ эмассиз!")
        return

    ad_id = int(callback.data.replace("approve_", ""))

    success = approve_ad(ad_id, callback.from_user.id)

    if not success:
        await callback.answer("⚠️ Бу эълон бошқа админ томонидан тасдиқланган!")
        return

    # ═══ ЭЪЛОН МАЪЛУМОТЛАРИНИ ОЛИШ ═══
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
            SELECT user_id, animal_type, quantity, price,
                   description, region, district, mfy, phone, username
            FROM ads WHERE id = {p}
        """, (ad_id,))
        ad = cursor.fetchone()

        if not ad:
            await callback.answer("❌ Эълон топилмади.")
            return

        user_id, a_type, qty, price, desc, region, dist, mfy, phone, username = ad

        bot_info = await bot.get_me()
        caption = (
            f"#️⃣ #{html.escape(a_type)}\n"
            f"🔢 <b>Сони:</b> {html.escape(qty)}\n"
            f"💰 <b>Нархи:</b> {html.escape(price)}\n"
            f"📝 <b>Изоҳ:</b> {html.escape(desc)}\n"
            f"📍 <b>Манзил:</b> {html.escape(region)} в, "
            f"{html.escape(dist)} т, "
            f"{html.escape(mfy)} МФЙ\n\n"
            f"📞 <b>Алоқа:</b> {html.escape(phone)}\n"
            f"💬 <b>Телеграм:</b> {username}\n\n"
            f"Канал: @internetmolbozor\n"
            f"Эълон жойланг: @{bot_info.username}"
        )
        
        # Медиаларни олиш (Энди база очиқ пайтда ишлайди)
        media_list = []
        cursor.execute(
            f"SELECT media_type, file_id FROM ad_media WHERE ad_id = {p}",
            (ad_id,)
        )
        db_media = cursor.fetchall()

        for m_type, m_file_id in db_media:
            media_list.append({"type": m_type, "file_id": m_file_id})

        if not media_list:
            if callback.message.photo:
                media_list.append({"type": "photo", "file_id": callback.message.photo[-1].file_id})
            elif callback.message.video:
                media_list.append({"type": "video", "file_id": callback.message.video.file_id})
                
    finally:
        # Базадан ҳамма нарса ўқиб бўлингач, уланишни хавфсиз ёпамиз
        conn.close()
    
    # ═══ КАНАЛГА ЮБОРИШ (АЛЬБОМ ЁКИ ОДДИЙ) ═══
    sent_msg_ids = []
    try:
        if len(media_list) > 1:
            # Агар бир нечта медиа бўлса (Альбом/Media Group)
            media_group = []
            for i, media in enumerate(media_list):
                if media["type"] == "photo":
                    media_group.append(InputMediaPhoto(
                        media=media["file_id"],
                        caption=caption if i == 0 else None,  # Матн фақат 1-медиага қўйилади
                        parse_mode="HTML"
                    ))
                elif media["type"] == "video":
                    media_group.append(InputMediaVideo(
                        media=media["file_id"],
                        caption=caption if i == 0 else None,
                        parse_mode="HTML"
                    ))
            
            sent_messages = await bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)
            # Матн бириктирилган биринчи хабар ID сини оламиз
            for msg in sent_messages:
                sent_msg_ids.append(str(msg.message_id))
            # Хабардорлик тизими (Notification) линки тўғри ишлаши учун 'sent' ўзгарувчисини эълон қиламиз
            sent = sent_messages[0]

        elif len(media_list) == 1:
            # Агар фақат 1 та расм ёки видео бўлса
            first_media = media_list[0]
            if first_media["type"] == "photo":
                sent = await bot.send_photo(
                    chat_id=CHANNEL_ID, photo=first_media["file_id"],
                    caption=caption, parse_mode="HTML"
                )
                sent_msg_ids.append(str(sent.message_id))
            elif first_media["type"] == "video":
                sent = await bot.send_video(
                    chat_id=CHANNEL_ID, video=first_media["file_id"],
                    caption=caption, parse_mode="HTML"
                )
                sent_msg_ids.append(str(sent.message_id))
        else:
            # Агар умуман медиа файл бўлмаса, фақат матн ўзи кетади
            sent = await bot.send_message(
                chat_id=CHANNEL_ID, text=caption, parse_mode="HTML"
            )
            sent_msg_ids.append(str(sent.message_id))

        # msg_id ни базага сақлаш (Сотилди тугмаси каналдаги постни таҳрирлаши учун)
        msg_ids_str = ",".join(sent_msg_ids)
        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE ads SET msg_id = {p} WHERE id = {p}",
            (msg_ids_str, ad_id)
        )
        conn.commit()
        conn.close()

    except Exception as e:
        logging.error(f"Каналга юборишда хато: {e}")
        await callback.answer("⚠️ Каналга юборишда хатолик бўлди.")
        return
        

    # ═══ ХАБАРДОРЛИК ТИЗИМИ (КАНАЛГА ЮБОРИЛГАНДАН KEYIN) ═══
    try:
        ad_price = parse_price_text(price)

        users = get_notification_users(
            animal_type=a_type,
            region=region,
            price=ad_price,
            district=dist
        )

        post_link = (
            f"https://t.me/internetmolbozor/"
            f"{sent.message_id}"
        )

        # Ёмон сўз текшириш
        notify_text = (
            f"{a_type} {region} {price} "
            f"{desc} {qty} {dist} {mfy}"
        )

        if not contains_bad_word(notify_text):
            for row in users:
                target_user_id = row[0]
                if target_user_id == user_id:
                    continue
                try:
                    await bot.send_message(
                        target_user_id,
                        f"🔔 *Сиз кузатаётган эълон топилди!*\n\n"
                        f"🐾 {html.escape(a_type)}\n"
                        f"📍 {html.escape(region)}\n"
                        f"💰 {html.escape(price)}\n\n"
                        f"📲 Кўриш:\n{post_link}",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
        else:
            logging.warning(
                f"Ножўя эълон хабардан тўсилди: ad_id={ad_id}"
            )

    except Exception as e:
        logging.error(f"Notification error: {e}")

    # ═══ АДМИН ЧАТИДАГИ ТУГМАЛАРНИ ЎЧИРИШ ВА МАТННИ ЯНГИЛАШ ═══
    text_content = (
        f"✅ *Эълон #{ad_id} тасдиқланди!*\n\n"
        f"🐾 {a_type}\n"
        f"📍 {region}\n"
        f"💰 {price}\n\n"
        f"Каналга жойланди."
    )
    
    try:
        # Агар расмли эълон бўлса (caption ўзгартирамиз)
        await callback.bot.edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text_content,
            parse_mode="Markdown",
            reply_markup=None
        )
    except Exception:
        try:
            # Агар оддий матнли эълон бўлса (text ўзгартирамиз)
            await callback.bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=text_content,
                parse_mode="Markdown",
                reply_markup=None
            )
        except Exception:
            # Агар иккаласи ҳам ўхшамаса, тугмаларни мажбурий ўчирамиз
            await callback.bot.edit_message_reply_markup(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=None
            )

    # ═══ ФОЙДАЛАНУВЧИГА ХАБАР ═══       
    try:
        post_link = f"https://t.me/internetmolbozor/{sent.message_id}"

        await bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ *Эълонингиз тасдиқланди!*\n\n"
                f"🐾 {a_type}\n"
                f"📍 {region}\n"
                f"💰 {price}\n\n"
                f"📢 <a href='{post_link}'>Каналда кўринг</a>\n\n"
                f"📅 Эълон <b>{AD_EXPIRE_DAYS} кун</b> актив бўлади."
            ),
            parse_mode="HTML"
        )
        logging.info(
            f"Фойдаланувчига хабар юборилди: "
            f"user_id={user_id}, ad_id={ad_id}"
        )
    except Exception as e:
        logging.error(
            f"Фойдаланувчига хабар юборилмади: "
            f"user_id={user_id}, ad_id={ad_id}, хато={e}"
        )

    # ═══ БОШҚА АДМИНЛАРНИНГ ХАБАРИНИ ЯНГИЛАШ ═══
    await _update_other_admins(
        ad_id, callback.from_user.id,
        f"✅ Админ @{callback.from_user.username or callback.from_user.id} "
        f"томонидан тасдиқланди."
    )

    await callback.answer("✅ Тасдиқланди!")


# ═══════════════════════════════════════
# РАД ҚИЛИШ КАЛЛБЕК
# ═══════════════════════════════════════

@router.callback_query(F.data.startswith("reject_"))
async def reject_ad_callback(callback: types.CallbackQuery):
    from config import REVIEW_ADMINS

    if callback.from_user.id not in REVIEW_ADMINS:
        await callback.answer("⛔ Сиз админ эмассиз!")
        return

    ad_id = int(callback.data.replace("reject_", ""))

    success = reject_ad(ad_id, callback.from_user.id)

    if not success:
        await callback.answer("⚠️ Бу эълон бошқа админ томонидан кўрилган!")
        return

    # ═══ ФОЙДАЛАНУВЧИНИ ОЛИШ ═══
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT user_id, animal_type, region, price FROM ads WHERE id = {p}",
        (ad_id,)
    )
    ad = cursor.fetchone()

    # ═══ БАЗАДАН ЎЧИРИШ ═══
    cursor.execute(f"DELETE FROM ads WHERE id = {p}", (ad_id,))
    conn.commit()
    conn.close()

    # ═══ АДМИНГА ХАБАР ═══
    try:
        await callback.message.edit_text(
            f"❌ *Эълон #{ad_id} рад этилди.*",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    # ═══ РАД СОНИНИ ОШИРИШ ВА БЛОК ТЕКШИРИШ ═══
    if ad:
        user_id, a_type, region, price = ad
        count, blocked = increment_rejection(user_id)

        # ═══ 1-ХОЛАТ: ФОЙДАЛАНУВЧИ БЛОККА ТУШДИ ═══
        if blocked:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🚫 *Сиз блокландингиз!*\n\n"
                        f"Эълонларингиз {count} марта "
                        f"админ томонидан рад этилган.\n\n"
                        f"Эълон бериш ҳуқуқингиз чекланди.\n"                        
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

            # Админларга фойдаланувчи блоклангани ҳақида хабар бериш
            for admin_id in REVIEW_ADMINS:
                if admin_id == callback.from_user.id:
                    continue
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=f"🚫 Фойдаланувчи ID:{user_id} блокланди ({count} марта рад)"
                    )
                except Exception:
                    pass

        # ═══ 2-ХОЛАТ: ОДДИЙ РАД ЭТИШ (Блок эмас, уринишлар бор) ═══
        else:
            try:
                remaining = MAX_REJECTIONS - count
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"❌ *Эълонингиз рад этилди.*\n\n"
                        f"🐾 {a_type}\n"
                        f"📍 {region}\n"
                        f"💰 {price}\n\n"
                        f"Сабаб: Эълон талабларга жавоб бермайди.\n"
                        f"Қайтадан ёзиб кўринг: /start\n\n"
                        f"⚠️ Диққат: {remaining} та уриниш қолди. "
                        f"Кейинги рад қилишда блокланасиз."
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    # ═══ БОШҚА АДМИНЛАРНИНГ ХАБАРИНИ ЯНГИЛАШ ═══
    await _update_other_admins(
        ad_id, callback.from_user.id,
        f"❌ Админ @{callback.from_user.username or callback.from_user.id} "
        f"томонидан рад этилди."
    )

    await callback.answer("❌ Рад этилди!")

# ═══════════════════════════════════════
# БОШҚА АДМИНЛАРНИНГ ХАБАРИНИ ЯНГИЛАШ
# ═══════════════════════════════════════

async def _update_other_admins(ad_id: int, acted_admin_id: int, status_text: str):
    """
    Хамма админдаги тасдиқлаш хабарини ЎЗИ ўзгартиради.
    Расм/видео бўлса caption, матн бўлса text ўзгартирилади.
    """
    rows = get_admin_review_messages(ad_id)

    new_text = (
        f"ℹ️ Эълон #{ad_id} кўрилди.\n\n"
        f"{status_text}"
    )

    for admin_id, message_id, chat_id in rows:
        if admin_id == acted_admin_id:
            continue  # Бу админники approve/reject ичида аллақачон ўзгарган

        edited = False

        # ═══ 1-УРИНИШ: caption ўзгартириш (расмли/видеоли хабар) ═══
        try:
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=new_text,
                parse_mode="Markdown",
                reply_markup=None
            )
            edited = True
        except Exception:
            pass

        # ═══ 2-УРИНИШ: text ўзгартириш (матнли хабар) ═══
        if not edited:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=new_text,
                    parse_mode="Markdown",
                    reply_markup=None
                )
                edited = True
            except Exception:
                pass

        # ═══ 3-УРИНИШ: Камида тугмаларни ўчириш ═══
        if not edited:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=None
                )
                edited = True
            except Exception as e:
                logging.error(
                    f"Админ {admin_id} хабарини таҳрирлашда "
                    f"хаммаси хато: {e}"
                )

    delete_admin_review_messages(ad_id)

# ═══════════════════════════════════════
# 🗂 МЕНИНГ ЭЪЛОНЛАРИМ
# ═══════════════════════════════════════

@router.message(F.text == "🗂 Менинг эълонларим")
async def my_ads(message: types.Message):
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    if __import__('os').getenv("DATABASE_URL"):
        cursor.execute(f"""
            SELECT id, animal_type, price, status,
                   expires_at,
                   EXTRACT(DAY FROM expires_at - NOW())::int AS days_left,
                   msg_id
            FROM ads
            WHERE user_id = {p} AND status = {p}
            ORDER BY id DESC
        """, (message.from_user.id, 'active'))
    else:
        cursor.execute(f"""
            SELECT id, animal_type, price, status,
                   expires_at,
                   CAST(julianday(expires_at) - julianday('now') AS INTEGER) AS days_left,
                   msg_id
            FROM ads
            WHERE user_id = {p} AND status = {p}
            ORDER BY id DESC
        """, (message.from_user.id, 'active'))
    ads = cursor.fetchall()
    conn.close()

    if not ads:
        await message.answer("Сизда ҳозирча актив эълонлар йўқ.")
        return

    await message.answer(
        f"📋 <b>Сизнинг актив эълонларингиз ({len(ads)} та):</b>",
        parse_mode="HTML"
    )

    for ad in ads:
        ad_id, a_type, price, status, expires_at, days_left, msg_id_str = ad

        # Муддат индикатори
        if days_left is not None and days_left <= 2:
            time_badge = f"🔴 {days_left} кун қолди"
        elif days_left is not None and days_left <= 5:
            time_badge = f"🟡 {days_left} кун қолди"
        else:
            time_badge = f"🟢 {days_left} кун қолди" if days_left else "🟢 Актив"

        buttons = [
            [
                InlineKeyboardButton(text="🤝 Сотилди", callback_data=f"sold_{ad_id}"),
                InlineKeyboardButton(text="❌ Ўчириш", callback_data=f"del_{ad_id}")
            ]
        ]
        if days_left is not None and days_left <= 2:
            if is_premium_user(message.from_user.id):
                buttons.append([
                    InlineKeyboardButton(
                        text="🔄 Каналга қайта жойлаш",
                        callback_data=f"repost_{ad_id}"
                    )
                ])
        inline_kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        channel_link = ""
        first_msg_id = None
        if msg_id_str:
            first_msg_id = str(msg_id_str).split(",")[0].strip()
            channel_link = f"\n📢 <a href='https://t.me/internetmolbozor/{first_msg_id}'>Каналда кўриш</a>"

        ad_text = (
            f"📦 <b>#{html.escape(a_type)}</b> — {html.escape(price)}\n"
            f"📅 {time_badge}"
            f"{channel_link}"
        )

        if first_msg_id and is_premium_user(message.from_user.id):
            # Премиум — ҳавола preview билан кўринади
            await message.answer(
                ad_text,
                parse_mode="HTML",
                disable_web_page_preview=False,
                reply_markup=inline_kb
            )
        else:
            # Оддий — preview ўчирилган
            await message.answer(
                ad_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=inline_kb
            )

# ═══════════════════════════════════════
# ИНЛАЙН CALLBACK — СОТИЛДИ / ЎЧИРИШ / УЗАЙТИРИШ
# ═══════════════════════════════════════

@router.callback_query(
    (F.data.startswith("sold_") | F.data.startswith("del_") | F.data.startswith("repost_"))
    & ~F.data.startswith("del_notif_")
    & ~F.data.startswith("edit_notif_")
)
async def handle_ad_action(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    action = parts[0]
    ad_id = parts[1]

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
            SELECT user_id, msg_id, animal_type, quantity, price, region, district, mfy, phone, username
            FROM ads WHERE id = {p}
        """, (int(ad_id),))
        ad = cursor.fetchone()

        if not ad:
            await callback.answer("Эълон топилмади.")
            return
            
        ad_owner_id = ad[0]
        if callback.from_user.id != ad_owner_id:
            await callback.answer("⛔ Сиз бу эълон эгаси эмассиз!")
            return

        msg_ids_str, a_type, qty, price, region, dist, mfy, phone, username = ad[1:]    
        msg_ids = [int(mid) for mid in str(msg_ids_str).split(",") if mid.strip().isdigit()]

        if action == "sold":
            cursor.execute(f"UPDATE ads SET status = 'sold' WHERE id = {p}", (ad_id,))
            conn.commit()

            if msg_ids:
                new_caption = (
                    f"🔴 <b>СОТИЛДИ!</b> 🔴\n\n"
                    f"#️⃣ #{html.escape(a_type)}\n"
                    f"🔢 <b>Сони:</b> {html.escape(qty)}\n"
                    f"💰 <b>Нархи:</b> {html.escape(price)}\n"
                    f"📍 <b>Манзил:</b> {html.escape(region)} в, {html.escape(dist)} т\n"
                    f"🤝 Харидорга барака берсин!"
                )
                try:
                    await bot.edit_message_caption(chat_id=CHANNEL_ID, message_id=msg_ids[0], caption=new_caption, parse_mode="HTML")
                    await callback.message.edit_text("✅ Каналда 'Сотилди' деб белгиланди.")
                except Exception:
                    await callback.answer("Постни таҳрирлаб бўлмади.")
            else:
                await callback.message.edit_text("✅ Эълон 'Сотилди' ҳолатига ўтказилди (каналдаги ИД топилмаганлиги сабабли).")

        elif action == "del":
            cursor.execute(f"UPDATE ads SET status = 'deleted' WHERE id = {p}", (ad_id,))
            conn.commit()

            for msg_id in msg_ids:
                try:
                    await bot.delete_message(chat_id=CHANNEL_ID, message_id=msg_id)
                except Exception:
                    pass
            await callback.message.edit_text("❌ Эълон каналдан бутунлай ўчирилди.")

        elif action == "repost":
            if not is_premium_user(callback.from_user.id):
                await callback.answer("⛔ Бу функция фақат Премиум эгалари учун!", show_alert=True)
                return

            # Алоҳида сўровлар учун жорий уланишни ёпиб турамиз
            conn.close()

            media_list_db = []
            conn2 = get_connection()
            cur2 = conn2.cursor()
            cur2.execute(
                f"SELECT media_type, file_id FROM ad_media WHERE ad_id = {get_placeholder()} ORDER BY id",
                (int(ad_id),)
            )
            media_list_db = cur2.fetchall()
            conn2.close()

            new_caption = (
                f"#️⃣ <b>#{html.escape(a_type)}</b>\n"
                f"🔢 <b>Сони:</b> {html.escape(qty)}\n"
                f"💰 <b>Нархи:</b> {html.escape(price)}\n"
                f"📍 <b>Манзил:</b> {html.escape(region)} в, {html.escape(dist)} т, {html.escape(mfy)} МФЙ\n"
                f"📞 {html.escape(phone)}"
            )

            new_msg_ids = []
            try:
                if media_list_db:
                    if len(media_list_db) == 1:
                        m_type, f_id = media_list_db[0]
                        if m_type == "photo":
                            sent = await bot.send_photo(CHANNEL_ID, photo=f_id, caption=new_caption, parse_mode="HTML")
                        else:
                            sent = await bot.send_video(CHANNEL_ID, video=f_id, caption=new_caption, parse_mode="HTML")
                        new_msg_ids.append(str(sent.message_id))
                    else:
                        media_group = []
                        for i, (m_type, f_id) in enumerate(media_list_db):
                            cap = new_caption if i == 0 else None
                            if m_type == "photo":
                                media_group.append(InputMediaPhoto(media=f_id, caption=cap, parse_mode="HTML"))
                            else:
                                media_group.append(InputMediaVideo(media=f_id, caption=cap, parse_mode="HTML"))
                        sent_msgs = await bot.send_media_group(CHANNEL_ID, media=media_group)
                        new_msg_ids = [str(m.message_id) for m in sent_msgs]
                else:
                    sent = await bot.send_message(CHANNEL_ID, text=new_caption, parse_mode="HTML")
                    new_msg_ids.append(str(sent.message_id))

                for old_msg_id in msg_ids:
                    try:
                        await bot.delete_message(chat_id=CHANNEL_ID, message_id=old_msg_id)
                    except Exception:
                        pass

                new_msg_str = ",".join(new_msg_ids)
                repost_ad(int(ad_id))
                conn3 = get_connection()
                cur3 = conn3.cursor()
                cur3.execute(
                    f"UPDATE ads SET msg_id = {get_placeholder()} WHERE id = {get_placeholder()}",
                    (new_msg_str, int(ad_id))
                )
                conn3.commit()
                conn3.close()

                await callback.message.edit_text(
                    f"✅ <b>{html.escape(a_type)}</b> эълони каналга қайта жойланди!\n\n"
                    f"📅 Яна <b>7 кун</b> актив бўлади.",
                    parse_mode="HTML"
                )
                await callback.answer("Қайта жойланди! ✅")

            except Exception as e:
                logging.error(f"Repost xato: {e}")
                await callback.answer("Хатолик юз берди.", show_alert=True)
    finally:
        # try-finally блоки орқали connection нинг ёпилиши 100% кафолатланади
        try:
            conn.close()
        except Exception:
            pass
