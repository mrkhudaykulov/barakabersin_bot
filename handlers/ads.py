import sqlite3
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
from database import contains_bad_word, parse_price_text, MIN_PRICE, MAX_PRICE, fmt_number, fix_keyboard_text, get_connection, get_placeholder

router = Router()


@router.message(F.text == "➕ Эълон бериш")
async def start_ad(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(AdStates.photo)
    await state.update_data(media_list=[])
    await message.answer(
        "Илтимос, ҳайвоннинг расмларини ёки видеосини юборинг "
        "(Бир нечта юборишингиз мумкин).\n\n"
        "Юбориб бўлгач '📥 Расмларни тасдиқлаш' тугмасини босинг:",
        reply_markup=cancel_keyboard()
    )


@router.message(AdStates.photo, F.photo | F.video)
async def process_photo(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    media_list = user_data.get("media_list", [])
    if message.photo:
        media_list.append({"type": "photo", "file_id": message.photo[-1].file_id})
    elif message.video:
        media_list.append({"type": "video", "file_id": message.video.file_id})
    await state.update_data(media_list=media_list)
    await message.answer(
        f"✅ {len(media_list)}-медиа қабул қилинди. "
        f"Яна юборишингиз мумкин. Тугатсангиз, пастки тугмани босинг:",
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

    # ═══ НАРХНИ ТЕКШИРИШ ═══
    price_value = parse_price_text(message.text)

    # Raqam umuman topilmadi
    if price_value == 0:
        await message.answer(
            "⚠️ Нарх топилмади. Илтимос, рақамда ёзинг:\n"
            "Масалан: `15000000` ёки `15 млн` ёки `15000 минг`",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
        return

    # Juda kichik
    if price_value < MIN_PRICE:
        await message.answer(
            f"⚠️ Нарх жуда кичик!\n\n"
            f"Камида *{fmt_number(MIN_PRICE)} сўм* бўлгани маъқул.\n"
            f"Қайтадан киритинг:",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
        return

    # Juda katta
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
        
    # ═══ БАРЧА ТЕКШИРИШДАН ЎТДИ ═══
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
        await state.update_data(description=message.text)
    await state.set_state(AdStates.phone)
    await message.answer(
        "Алоқа учун телефон рақамингизни юборинг:",
        reply_markup=phone_keyboard()
    )


@router.message(AdStates.phone, F.contact | F.text)
async def process_phone(message: types.Message, state: FSMContext):
    if message.text and not any(char.isdigit() for char in message.text):
        await message.answer(
            "⚠️ Илтимос, телефон рақамни тўғри форматда ёзинг.",
            reply_markup=phone_keyboard()
        )
        return

    phone = message.contact.phone_number if message.contact else message.text
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
                "Илтимос, қайтадан тоза матн билан ёзинг.\n"
                "Ҳайвон сотиш бўлимида илтимос одобли бўлинг.",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
            await state.clear()
            return
    
    
    
    if message.from_user.username:
        username_text = f"@{message.from_user.username}"
    else:
        username_text = (
            f"<a href='tg://user?id={message.from_user.id}'>"
            f"{message.from_user.full_name}</a> (Ник йўқ)"
        )

    bot_info = await bot.get_me()
    caption = (
        f"#️⃣ #{data['animal_type']}\n"
        f"🔢 <b>Сони:</b> {data['quantity']}\n"
        f"💰 <b>Нархи:</b> {data['price']}\n"
        f"📝 <b>Изоҳ:</b> {data['description']}\n"
        f"📍 <b>Манзил:</b> {data['region']} в, "
        f"{data['district']} т, {data['mfy']} МФЙ\n\n"
        f"📞 <b>Алоқа:</b> {phone}\n"
        f"💬 <b>Телеграм:</b> {username_text}\n\n"
        f"Админсиз эълон жойлаш: @{bot_info.username}\n"
        f"Канал: @internetmolbozor"
    )

    media_list = data.get("media_list", [])

    try:
        telegram_media = []
        for i, media in enumerate(media_list):
            if media["type"] == "photo":
                telegram_media.append(InputMediaPhoto(
                    media=media["file_id"],
                    caption=caption if i == 0 else "",
                    parse_mode="HTML"
                ))
            elif media["type"] == "video":
                telegram_media.append(InputMediaVideo(
                    media=media["file_id"],
                    caption=caption if i == 0 else "",
                    parse_mode="HTML"
                ))

        sent_messages = await bot.send_media_group(
            chat_id=CHANNEL_ID, media=telegram_media
        )
        msg_ids_str = ",".join([str(msg.message_id) for msg in sent_messages])

        db_username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else f"ID: {message.from_user.id}"
        )

        p = get_placeholder()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO ads
            (user_id, msg_id, animal_type, quantity, price,
             description, region, district, mfy, phone, username)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
        """, (
            message.from_user.id, msg_ids_str,
            data['animal_type'], data['quantity'], data['price'],
            data['description'], data['region'], data['district'],
            data['mfy'], phone, db_username
        ))
        conn.commit()
        conn.close()

        await message.answer(
            "🎉 Эълонингиз @internetmolbozor каналига муваффақиятли жойланди!",
            reply_markup=main_menu()
        )
    except Exception as e:
        await message.answer(f"Хатолик юз берди: {e}", reply_markup=main_menu())

    await state.clear()


# ═══════════════════════════════════════
# МЕНИНГ ЭЪЛОНЛАРИМ
# ═══════════════════════════════════════

@router.message(F.text == "🗂 Менинг эълонларим")
async def my_ads(message: types.Message):
    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    f"""
    SELECT id, animal_type, price, status FROM ads WHERE user_id = {p} AND status = {p}
""", (message.from_user.id, 'active'))
    
    ads = cursor.fetchall()
    conn.close()

    if not ads:
        await message.answer("Сизда ҳозирча актив эълонлар йўқ.")
        return

    await message.answer("Сизнинг актив эълонларингиз:")
    for ad in ads:
        ad_id, a_type, price, status = ad
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🤝 Сотилди", callback_data=f"sold_{ad_id}"),
            InlineKeyboardButton(text="❌ Ўчириш", callback_data=f"del_{ad_id}")
        ]])
        await message.answer(
            f"📦 #{a_type} - {price}",
            reply_markup=inline_kb
        )


# ═══════════════════════════════════════
# ИНЛАЙН CALLBACK
# ═══════════════════════════════════════

@router.callback_query(F.data.startswith("sold_") | F.data.startswith("del_"))
async def handle_ad_action(callback: types.CallbackQuery):
    action, ad_id = callback.data.split("_")

    p = get_placeholder()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT msg_id, animal_type, quantity, price, region, district, mfy, phone, username
        FROM ads WHERE id = {p}
    """, (int(ad_id),))
    
    ad = cursor.fetchone()

    if not ad:
        await callback.answer("Эълон топилмади.")
        conn.close()
        return

    msg_ids_str, a_type, qty, price, region, dist, mfy, phone, username = ad
    msg_ids = [int(mid) for mid in str(msg_ids_str).split(",")]

    if action == "sold":
        cursor.execute(
            f"UPDATE ads SET status = 'sold' WHERE id = {p}",
            (ad_id,)
        )
        conn.commit()

        new_caption = (
            f"🔴 <b>СОТИЛДИ!</b> 🔴\n\n"
            f"#️⃣ #{a_type}\n"
            f"🔢 <b>Сони:</b> {qty}\n"
            f"💰 <b>Нархи:</b> {price}\n"
            f"📍 <b>Манзил:</b> {region} в, {dist} т\n"
            f"🤝 Харидорга барака берсин!"
        )
        try:
            await bot.edit_message_caption(
                chat_id=CHANNEL_ID,
                message_id=msg_ids[0],
                caption=new_caption,
                parse_mode="HTML"
            )
            await callback.message.edit_text(
                "✅ Каналда 'Сотилди' деб белгиланди."
            )
        except Exception:
            await callback.answer("Постни таҳрирлаб бўлмади.")

    elif action == "del":
        cursor.execute(
            f"UPDATE ads SET status = 'deleted' WHERE id = {p}",
            (ad_id,)
        )
        conn.commit()

        for msg_id in msg_ids:
            try:
                await bot.delete_message(
                    chat_id=CHANNEL_ID, message_id=msg_id
                )
            except Exception:
                pass
        await callback.message.edit_text(
            "❌ Эълон каналдан бутунлай ўчирилди."
        )

    conn.close()
