import logging
import sqlite3

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from keyboards import (
    main_menu, calc_menu_keyboard, standard_step_keyboard,
    calc_qoramol_direction_keyboard, photo_confirm_keyboard,
    animal_types_keyboard, regions_keyboard, districts_keyboard,
    description_keyboard, search_animal_keyboard
)
from states import AdStates, CalcStates, SearchStates, PriceInputStates

router = Router()


@dp_message_start = router.message(Command("start"))
async def start_cmd(message: types.Message):
    conn = sqlite3.connect("chorva.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (message.from_user.id,)
        )
        conn.commit()
    except Exception as e:
        logging.error(f"Базага ёзишда хатолик: {e}")
    finally:
        conn.close()

    await message.answer(
        "Ассалому алайкум! Чорва бозор ботига хуш келибсиз.",
        reply_markup=main_menu()
    )


@router.message(F.text == "🏠 Бош меню")
async def home_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Асосий меню", reply_markup=main_menu())


# ═══════════════════════════════════════
# 🎛 МАРКАЗЛАШТИРИЛГАН НАВИГАЦИЯ
# ═══════════════════════════════════════

@router.message(F.text == "❌ Бекор қилиш")
async def global_cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ Фаол жараён мавжуд эмас.", reply_markup=main_menu())
        return

    # Калькулятор бўлимлари
    if current_state in [
        CalcStates.menu.state, CalcStates.qoy_bosh.state,
        CalcStates.qoy_narx.state, CalcStates.qoy_qozi_narx.state,
        CalcStates.qoy_em_narx.state, CalcStates.qm_bosh.state,
        CalcStates.qm_yon.state, CalcStates.qm_sut_vazn.state,
        CalcStates.qm_narx.state, CalcStates.qm_em_narx.state
    ]:
        await state.set_state(CalcStates.menu)
        await message.answer(
            "🌾 *Чорвачилик калькулятори* бош менюси:",
            parse_mode="Markdown",
            reply_markup=calc_menu_keyboard()
        )
        return

    # Қидириш
    if current_state and current_state.startswith("SearchStates"):
        await state.clear()
        await message.answer("❌ Қидириш бекор қилинди.", reply_markup=main_menu())
        return

    # Нарх киритиш
    if current_state and current_state.startswith("PriceInputStates"):
        await state.clear()
        await message.answer("❌ Нарх киритиш бекор қилинди.", reply_markup=main_menu())
        return

    # Қолган ҳолатлар (эълон бериш ва бошқалар)
    await state.clear()
    await message.answer("❌ Жараён бекор қилинди.", reply_markup=main_menu())


@router.message(F.text == "🔙 Орқага")
async def global_back_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ Фаол жараён мавжуд эмас.", reply_markup=main_menu())
        return

    # ═══ Қидириш ═══
    if current_state == SearchStates.animal_type.state:
        await state.clear()
        await message.answer("🏠 Асосий меню", reply_markup=main_menu())
        return

    elif current_state == SearchStates.region.state:
        await state.set_state(SearchStates.animal_type)
        await message.answer(
            "🔙 Ҳайвон турини қайта танланг:",
            reply_markup=search_animal_keyboard()
        )
        return

    # ═══ Нарх киритиш ═══
    elif current_state == PriceInputStates.animal_type.state:
        await state.clear()
        await message.answer("🏠 Асосий меню", reply_markup=main_menu())
        return

    elif current_state == PriceInputStates.region.state:
        await state.set_state(PriceInputStates.animal_type)
        await message.answer(
            "🔙 Ҳайвон турини қайта танланг:",
            reply_markup=search_animal_keyboard()
        )
        return

    elif current_state == PriceInputStates.price.state:
        await state.set_state(PriceInputStates.region)
        await message.answer(
            "🔙 Вилоятни қайта танланг:",
            reply_markup=regions_keyboard()
        )
        return

    # ═══ Қўй калькулятори ═══
    elif current_state == CalcStates.qoy_bosh.state:
        await state.set_state(CalcStates.menu)
        await message.answer(
            "🌾 *Чорвачилик калькулятори* бўлимига хуш килибсиз.\nНимани ҳисобламоқчисиз?",
            parse_mode="Markdown",
            reply_markup=calc_menu_keyboard()
        )
        return

    elif current_state == CalcStates.qoy_narx.state:
        await state.set_state(CalcStates.qoy_bosh)
        await message.answer(
            "1️⃣ *Совлиқ қўйлар сонини* киритинг:\n_(масалан: 20)_",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
        return

    elif current_state == CalcStates.qoy_qozi_narx.state:
        await state.set_state(CalcStates.qoy_narx)
        await message.answer(
            "2️⃣ *1 та совлиқ қўй ўртача нархини* киритинг (сўм):\n_(масалан: 3 500 000)_",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
        return

    elif current_state == CalcStates.qoy_em_narx.state:
        await state.set_state(CalcStates.qoy_qozi_narx)
        await message.answer(
            "3️⃣ *1 та қўзининг сотилиш нархини* киритинг (сўм):\n_(масалан: 1 200 000)_",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
        return

    # ═══ Қорамол калькулятори ═══
    elif current_state == CalcStates.qm_bosh.state:
        await state.set_state(CalcStates.menu)
        await message.answer(
            "🌾 *Чорвачилик калькулятори* бўлимига хуш келибсиз.\nНимани ҳисобламоқчисиз?",
            parse_mode="Markdown",
            reply_markup=calc_menu_keyboard()
        )
        return

    elif current_state == CalcStates.qm_yon.state:
        await state.set_state(CalcStates.qm_bosh)
        await message.answer(
            "1️⃣ *Сигирлар (ёки она моллар) сонини* киритинг:\n_(масалан: 10)_",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
        return

    elif current_state == CalcStates.qm_sut_vazn.state:
        await state.set_state(CalcStates.qm_yon)
        await message.answer(
            "2️⃣ *Йўналишни танланг:*",
            reply_markup=calc_qoramol_direction_keyboard()
        )
        return

    elif current_state == CalcStates.qm_narx.state:
        await state.set_state(CalcStates.qm_sut_vazn)
        data = await state.get_data()
        if data.get("qm_yon") == "sut":
            await message.answer(
                "3️⃣ *1 та сигирнинг кунлик сут миқдорини* киритинг (литр):\n_(масалан: 15)_",
                parse_mode="Markdown",
                reply_markup=standard_step_keyboard()
            )
        else:
            await message.answer(
                "3️⃣ *1 та молнинг ўртача тирик вазнини* киритинг (кг):\n_(масалан: 400)_",
                parse_mode="Markdown",
                reply_markup=standard_step_keyboard()
            )
        return

    elif current_state == CalcStates.qm_em_narx.state:
        await state.set_state(CalcStates.qm_narx)
        data = await state.get_data()
        if data.get("qm_yon") == "sut":
            await message.answer(
                "4️⃣ *1 литр сут сотилиш нархини* киритинг (сўм):\n_(масалан: 4 500)_",
                parse_mode="Markdown",
                reply_markup=standard_step_keyboard()
            )
        else:
            await message.answer(
                "4️⃣ *1 кг тирик вазн нархини* киритинг (сўм):\n_(масалан: 25 000)_",
                parse_mode="Markdown",
                reply_markup=standard_step_keyboard()
            )
        return

    # ═══ Эълон бериш ═══
    elif current_state == AdStates.animal_type.state:
        await state.set_state(AdStates.photo)
        await message.answer(
            "🔙 Расм юбориш босқичига қайтилди:",
            reply_markup=photo_confirm_keyboard()
        )
        return

    elif current_state == AdStates.region.state:
        await state.set_state(AdStates.animal_type)
        await message.answer(
            "🔙 Ҳайвон турини қайта танланг:",
            reply_markup=animal_types_keyboard()
        )
        return

    elif current_state == AdStates.district.state:
        await state.set_state(AdStates.region)
        await message.answer(
            "🔙 Вилоятни қайта танланг:",
            reply_markup=regions_keyboard()
        )
        return

    elif current_state == AdStates.mfy.state:
        data = await state.get_data()
        await state.set_state(AdStates.district)
        await message.answer(
            "🔙 Туманни қайта танланг:",
            reply_markup=districts_keyboard(data.get('region'))
        )
        return

    elif current_state == AdStates.quantity.state:
        await state.set_state(AdStates.mfy)
        await message.answer(
            "🔙 МФЙ номини қайта ёзинг:",
            reply_markup=standard_step_keyboard()
        )
        return

    elif current_state == AdStates.price.state:
        await state.set_state(AdStates.quantity)
        await message.answer(
            "🔙 Сонини қайта киритинг:",
            reply_markup=standard_step_keyboard()
        )
        return

    elif current_state == AdStates.description.state:
        await state.set_state(AdStates.price)
        await message.answer(
            "🔙 Нархини қайта киритинг:",
            reply_markup=standard_step_keyboard()
        )
        return

    elif current_state == AdStates.phone.state:
        await state.set_state(AdStates.description)
        await message.answer(
            "🔙 Изоҳ бўлимига қайтилди:",
            reply_markup=description_keyboard()
        )
        return
