from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup

from config import bot
from states import NotifyStates
from keyboards import (
    search_animal_keyboard,
    animal_types_keyboard, 
    regions_keyboard,
    regions_with_all_keyboard,
    notification_districts_keyboard,
    main_menu,
    notify_menu_keyboard,
    standard_step_keyboard
)

from database import (
    get_connection,
    get_placeholder,
    parse_price_text,
    fix_keyboard_text,
    get_user_notifications,
    fmt_number,
    delete_notification
)

router = Router()


@router.message(F.text == "🔔 Хабардор қил")
async def notify_start(message: types.Message):

    await message.answer(
        "🔔 Хабарнома маркази\n\n"
        "Бу марказ орқали Сиз эълонлар ҳақида "
        "ЭСЛАТМАлар олиб туришингиз ва кузатишингиз мумкин",
        reply_markup=notify_menu_keyboard()
    )

@router.message(F.text == "➕ Янги кузатув")
async def create_notification(
    message: types.Message,
    state: FSMContext
):

    await state.set_state(
        NotifyStates.animal_type
    )

    await message.answer(
        "Қайси чорва ҳақида хабардор қилиш керак?",
        reply_markup=search_animal_keyboard()
    )

@router.message(NotifyStates.animal_type)
async def notify_animal(message: types.Message, state: FSMContext):

    if message.text == "❌ Бекор қилиш":
        await state.clear()
        await message.answer("❌ Бекор қилинди.", reply_markup=main_menu())
        return

    # ➕ КИРИТИЛГАН ЎЗГАРТИРИШ (Валидация):
    valid_types = ["Буқа", "Сигир", "Тана", "Бузоқ", "Қўчқор", "Совлиқ", "Қўзи", "Эчки", "От", "Туя", "Парранда", "Барчаси"]
    if message.text not in valid_types:
        await message.answer(
            "⚠️ Тугмалардан бирини танланг:",
            reply_markup=search_animal_keyboard()
        )
        return

    await state.update_data(animal_type=fix_keyboard_text(message.text))
    await state.set_state(NotifyStates.region)
    await message.answer("Қайси вилоят бўйича?", reply_markup=regions_keyboard())


@router.message(NotifyStates.region)
async def notify_region(message: types.Message, state: FSMContext):
    if message.text == "❌ Бекор қилиш":
        await state.clear()
        await message.answer("❌ Бекор қилинди.", reply_markup=main_menu())
        return

    if message.text == "🔙 Орқага":
        await state.set_state(NotifyStates.animal_type)
        await message.answer(
            "Қайси чорва ҳақида хабардор қилиш керак?",
            reply_markup=search_animal_keyboard()
        )
        return
    
    region_fixed=fix_keyboard_text(message.text)
    await state.update_data(region=region_fixed)
    await state.set_state(NotifyStates.district)
    await message.answer(
        "🏘 Қайси туманда қидирилади?\n\n"
        "Ёки, *📍 Барчаси* тугмасини танланг.",
        parse_mode="Markdown",
        reply_markup=notification_districts_keyboard(region_fixed)
    )

@router.message(NotifyStates.district)
async def notify_district(message: types.Message, state: FSMContext):
    if message.text == "❌ Бекор қилиш":
        await state.clear()
        await message.answer("❌ Бекор қилинди.", reply_markup=main_menu())
        return

    if message.text == "🔙 Орқага":
        await state.set_state(NotifyStates.region)
        await message.answer(
            "Қайси вилоят бўйича хабардор қилиш керак?", 
            reply_markup=regions_keyboard()
        )
        return

    await state.update_data(district=message.text)
    await state.set_state(NotifyStates.min_price)
    await message.answer(
        "Минимал (энг паст) нархи қанча бўлсин?\n\n*Масалан:* 5 000 000 ёки 5млн",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )

@router.message(NotifyStates.min_price)
async def notify_min_price(message: types.Message, state: FSMContext):
    # 3. ➕ Нарх босқичида "Орқага" босилса, қайтадан Туман сўраш блоки
    if message.text == "🔙 Орқага":
        user_data = await state.get_data()
        saved_region = user_data.get("region", "Тошкент") # Агар вилоят топилмаса хато бермаслиги учун
        
        await state.set_state(NotifyStates.district)
        await message.answer(
            "🏘 Қайси туманда қидирилади?\n\nАгар фарқи бўлмаса, *📍 Барчаси* танланг.",
            parse_mode="Markdown",
            reply_markup=notification_districts_keyboard(saved_region)
        )
        return

    if message.text == "❌ Бекор қилиш":
        await state.clear()
        await message.answer("❌ Бекор қилинди.", reply_markup=main_menu())
        return

    # Нархни парсинг қилиш ва текшириш қисми (ўзингизнинг кодингиз)
    price = parse_price_text(message.text)

    if price <= 0:
        await message.answer(
            "Нархни тўғри киритинг.",
            reply_markup=standard_step_keyboard()
        )
        return

    await state.update_data(min_price=price)
    await state.set_state(NotifyStates.max_price)

    await message.answer(
        "Максимал (энг баланд) нархи қанча бўлсин?",
        reply_markup=standard_step_keyboard()
    )
    

@router.message(NotifyStates.max_price)
async def notify_max_price(message: types.Message, state: FSMContext):
    # ═══ ➕ НАВИГАЦИЯ ТЕКШИРУВИ (ҚЎШИЛДИ) ═══
    if message.text == "🔙 Орқага":
        await state.set_state(NotifyStates.min_price)
        await message.answer(
            "Минимал (энг паст) нархи қанча бўлсин?",
            reply_markup=standard_step_keyboard()
        )
        return

    if message.text == "❌ Бекор қилиш":
        await state.clear()
        await message.answer("❌ Бекор қилинди.", reply_markup=main_menu())
        return
        
    max_price = parse_price_text(message.text)

    if max_price <= 0:
        await message.answer(
            "Нархни тўғри киритинг.",
            reply_markup=standard_step_keyboard()
        )
        return

    data = await state.get_data()

    if max_price < data["min_price"]:
        await message.answer(
            "Максимал нарх минимал нархдан катта бўлиши керак.\nҚайтадан киритинг:",
            reply_markup=standard_step_keyboard()
        )
        return
   
    conn = get_connection()
    cur = conn.cursor()

    p = get_placeholder()

    
    cur.execute(
        f"""
        SELECT id
        FROM notifications
        WHERE user_id = {p}
        AND animal_type = {p}
        AND region = {p}
        AND district = {p}
        AND min_price = {p}
        AND max_price = {p}
        """,
        (
            message.from_user.id,
            data["animal_type"],
            data["region"],
            data.get("district", "📍 Барчаси"),
            data["min_price"],
            max_price
        )
    )
    
    exists = cur.fetchone()
    
    if exists:
        conn.close()
    
        await message.answer(
            "⚠️ Бу эслатма аввал яратилган.",
            reply_markup=main_menu()
        )
        return
        
    cur.execute(
        f"""
        INSERT INTO notifications
        (user_id, animal_type, region, district, min_price, max_price)
        VALUES ({p},{p},{p},{p},{p},{p})
        """,
        (
            message.from_user.id,
            data["animal_type"],
            data["region"],
            data.get("district", "📍 Барчаси"),
            data["min_price"],
            max_price
        )
    )
    conn.commit()
    conn.close()

    await state.clear()

    await message.answer(
        "✅ Эслатма сақланди.\n\n"
        "Мос эълон чиқса автомат хабар қиламиз!",
        reply_markup=main_menu()
    )


# ═══════════════════════════════════════
# 📌 МЕНИНГ КУЗАТУВЛАРИМ — РЎЙХАТ
# ═══════════════════════════════════════

@router.message(F.text == "📌 Менинг кузатувларим")
async def my_notifications(message: types.Message):
    notifications = get_user_notifications(message.from_user.id)

    if not notifications:
        await message.answer(
            "📭 Сизда ҳозирча кузатувлар мавжуд эмас.\n\n"
            "➕ Янги кузатув яратиш учун тугмани босинг.",
            reply_markup=notify_menu_keyboard()
        )
        return

    await message.answer(
        f"📌 *Сизнинг кузатувларингиз ({len(notifications)} та):*\n\n"
        f"_Ўчириш учун тугмани босинг:_",
        parse_mode="Markdown"
    )

    for n in notifications:
        notif_id, animal, region, district, min_p, max_p = n[0], n[1], n[2], n[3], n[4], n[5]
        
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Таҳрирлаш",
                    callback_data=f"edit_notif_{notif_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Ўчириш",
                    callback_data=f"del_notif_{notif_id}"
                )
            ]
        ])
        
        district_text = district if district and district != "Барчаси" else "Барчаси"
        await message.answer(
            f"🐾 *{animal}*\n"
            f"📍 {region} в, {district_text}\n"
            f"💰 {fmt_number(min_p)} — {fmt_number(max_p)} сўм",
            parse_mode="Markdown",
            reply_markup=inline_kb
        )


# ═══════════════════════════════════════
# ❌ КУЗАТУВНИ ЎЧИРИШ (CALLBACK)
# ═══════════════════════════════════════

@router.callback_query(F.data.startswith("del_notif_"))
async def delete_notification_callback(callback: types.CallbackQuery):
    notif_id = int(callback.data.replace("del_notif_", ""))

    # ═══ ТЕКШИРИШ — ФАҚАТ ЭГАСИ ЎЧИРА ОЛАДИ ═══
    p = get_placeholder()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT user_id FROM notifications WHERE id = {p}",
        (notif_id,)
    )
    row = cur.fetchone()

    if not row or row[0] != callback.from_user.id:
        await callback.answer("⛔ Сиз бу кузатув эгаси эмассиз!")
        conn.close()
        return

    cur.execute(f"DELETE FROM notifications WHERE id = {p}", (notif_id,))
    conn.commit()
    conn.close()

    await callback.message.edit_text("🗑 Кузатув ўчирилди.")
    await callback.answer("Ўчирилди ✅")


# ═══════════════════════════════════════
# ✏️ КУЗАТУВНИ ТАҲРИРЛАШ (CALLBACK)
# ═══════════════════════════════════════

@router.callback_query(F.data.startswith("edit_notif_"))
async def edit_notification_start(callback: types.CallbackQuery, state: FSMContext):
    notif_id = int(callback.data.replace("edit_notif_", ""))

    # ═══ ТЕКШИРИШ — ФАҚАТ ЭГАСИ ТАҲРИРЛАЙ ОЛАДИ ═══
    p = get_placeholder()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT user_id FROM notifications WHERE id = {p}",
        (notif_id,)
    )
    row = cur.fetchone()

    if not row or row[0] != callback.from_user.id:
        await callback.answer("⛔ Сиз бу кузатув эгаси эмассиз!")
        conn.close()
        return
    conn.close()

    await state.set_state(NotifyStates.edit_min_price)
    await state.update_data(edit_notif_id=notif_id)
    await callback.message.answer(
        "✏️ Янги *минимал нархни* киритинг:\n_(масалан: 3000000)_",
        parse_mode="Markdown"
    )
    await callback.answer()
    


@router.message(NotifyStates.edit_min_price)
async def edit_min_price(message: types.Message, state: FSMContext):
    price = parse_price_text(message.text)

    if price <= 0:
        await message.answer("⚠️ Нархни тўғри рақамда киритинг:")
        return

    await state.update_data(edit_min_price=price)
    await state.set_state(NotifyStates.edit_max_price)

    await message.answer(
        "✏️ Янги *максимал нархни* киритинг:\n_(масалан: 10000000)_",
        parse_mode="Markdown"
    )


@router.message(NotifyStates.edit_max_price)
async def edit_max_price(message: types.Message, state: FSMContext):
    max_price = parse_price_text(message.text)

    if max_price <= 0:
        await message.answer("⚠️ Нархни тўғри рақамда киритинг:")
        return

    data = await state.get_data()
    min_price = data.get("edit_min_price")

    if max_price < min_price:
        await message.answer(
            "⚠️ Максимал нарх минимал нархдан катта бўлиши керак:"
        )
        return

    notif_id = data.get("edit_notif_id")

    # Базани янгилаш
    p = get_placeholder()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE notifications
        SET min_price = {p}, max_price = {p}
        WHERE id = {p}
        """,
        (min_price, max_price, notif_id)
    )
    conn.commit()
    conn.close()

    await state.clear()

    await message.answer(
        f"✅ *Кузатув янгиланди!*\n\n"
        f"💰 {fmt_number(min_price)} — {fmt_number(max_price)} сўм",
        parse_mode="Markdown",
        reply_markup=notify_menu_keyboard()
    )
'''
@router.message(NotifyStates.animal_type)
async def notify_animal_fallback(message: types.Message, state: FSMContext):
    """Kuzatuv — hayvon turida noto'g'ri matn"""
    await message.answer(
        "⚠️ Тугмалардан бирини танланг:",
        reply_markup=search_animal_keyboard()
    )


@router.message(NotifyStates.region)
async def notify_region_fallback(message: types.Message, state: FSMContext):
    """Kuzatuv — viloyatda noto'g'ri matn"""
    await message.answer(
        "⚠️ Тугмалардан бирини танланг:",
        reply_markup=regions_keyboard()
    )
'''

@router.message(NotifyStates.min_price)
async def notify_min_fallback(message: types.Message, state: FSMContext):
    """Kuzatuv — min narxda noto'g'ri matn"""
    await message.answer(
        "⚠️ Минимал нархни рақамда киритинг:\nМасалан: 3000000"
    )


@router.message(NotifyStates.max_price)
async def notify_max_fallback(message: types.Message, state: FSMContext):
    """Kuzatuv — max narxda noto'g'ri matn"""
    await message.answer(
        "⚠️ Максимал нархни рақамда киритинг:\nМасалан: 10000000"
    )

