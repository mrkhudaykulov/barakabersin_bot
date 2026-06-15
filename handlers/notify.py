from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from states import NotifyStates
from keyboards import (
    search_animal_keyboard,
    regions_keyboard,
    main_menu,
    notify_menu_keyboard
)

from database import (
    get_connection,
    get_placeholder,
    parse_price_text,
    fix_keyboard_text,
    get_user_notifications
)

router = Router()


@router.message(F.text == "🔔 Хабардор қил")
async def notify_start(message: types.Message):

    await message.answer(
        "🔔 Хабарнома маркази \n",
        "Бу марказ орқали Сиз эълонлар ҳақида ЭСЛАТМАлар олиб туришингиз ва кузатишингиз мумкин \n",
        
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

    await state.update_data(
        animal_type=fix_keyboard_text(message.text)
    )

    await state.set_state(
        NotifyStates.region
    )

    await message.answer(
        "Қайси вилоят бўйича?",
        reply_markup=regions_keyboard()
    )



@router.message(NotifyStates.region)
async def notify_region(message: types.Message, state: FSMContext):

    await state.update_data(
        region=fix_keyboard_text(message.text)
    )

    await state.set_state(
        NotifyStates.min_price
    )

    await message.answer(
        "Минимал (энг паст) нархи қанча бўлсин?\n\nМасалан:\n3000000"
    )

@router.message(NotifyStates.min_price)
async def notify_min_price(message: types.Message, state: FSMContext):

    price = parse_price_text(message.text)

    if price <= 0:
        await message.answer(
            "Нархни тўғри киритинг."
        )
        return

    await state.update_data(
        min_price=price
    )

    await state.set_state(
        NotifyStates.max_price
    )

    await message.answer(
        "Максимал (энг баланд) нархи қанча бўлсин?"
    )

@router.message(NotifyStates.max_price)
async def notify_max_price(message: types.Message, state: FSMContext):

    max_price = parse_price_text(message.text)

    if max_price <= 0:
        await message.answer(
            "Нархни тўғри киритинг."
        )
        return

    data = await state.get_data()

    if max_price < data["min_price"]:
        await message.answer(
            "Максимал нарх минимал нархдан катта бўлиши керак."
        )
        return

    data = await state.get_data()

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
        AND min_price = {p}
        AND max_price = {p}
        """,
        (
            message.from_user.id,
            data["animal_type"],
            data["region"],
            data["min_price"],
            max_price
        )
    )
    
    exists = cur.fetchone()
    
    if exists:
        conn.close()
    
        await message.answer(
            "⚠️ Бу эслатма аввал яратилган."
        )
        return
    
    
    
    cur.execute(
        f"""
        INSERT INTO notifications
        (
            user_id,
            animal_type,
            region,
            min_price,
            max_price
        )
        VALUES
        (
            {p},{p},{p},{p},{p}
        )
        """,
        (
            message.from_user.id,
            data["animal_type"],
            data["region"],
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


@router.message(F.text == "📌 Менинг кузатувларим")
async def my_notifications(message: types.Message):

    notifications = get_user_notifications(
        message.from_user.id
    )

    if not notifications:
        await message.answer(
            "Сизда ҳозирча кузатувлар мавжуд эмас."
        )
        return

    text = "📌 Сизнинг кузатувларингиз:\n\n"

    for n in notifications:
        text += (
            f"🐾 {n[1]}\n"
            f"📍 {n[2]}\n"
            f"💰 {n[3]:,} - {n[4]:,}\n\n"
        )

    await message.answer(text)

