import logging

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from calculators import qoy_hisobla, qm_hisobla_sut, qm_hisobla_gosht
from states import CalcStates
from keyboards import (
    calc_menu_keyboard, standard_step_keyboard,
    calc_qoramol_direction_keyboard
)

router = Router()
router.message.filter(F.chat.type == "private")

@router.message(F.text == "🧮 Ферма калькулятори")
async def calc_main_menu(message: types.Message, state: FSMContext):
    await state.set_state(CalcStates.menu)
    await message.answer(
        "🌾 *Чорвачилик калькулятори* бўлимига хуш келибсиз.\n"
        "Нимани ҳисобламоқчисиз?",
        parse_mode="Markdown",
        reply_markup=calc_menu_keyboard()
    )


# ═══════════════════════════════════════
# 🐑 ҚЎЙ КАЛЬКУЛЯТОРИ
# ═══════════════════════════════════════

@router.message(CalcStates.menu, F.text == "🐑 Қўй калькулятори")
async def qoy_start(message: types.Message, state: FSMContext):
    await state.set_state(CalcStates.qoy_bosh)
    await message.answer(
        "🐑 *Қўй фермаси калькулятори*\n\n"
        "1️⃣ *Совлиқ қўйлар сонини* киритинг:\n_(масалан: 20)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(CalcStates.qoy_bosh)
async def qoy_bosh_process(message: types.Message, state: FSMContext):
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Илтимос, тўғри сон киритинг:")
        return

    await state.update_data(qoy_bosh=int(val))
    await state.set_state(CalcStates.qoy_narx)
    await message.answer(
        "2️⃣ *1 та совлиқ қўй ўртача нархини* киритинг (сўм):\n"
        "_(масалан: 3 500 000)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(CalcStates.qoy_narx)
async def qoy_narx_process(message: types.Message, state: FSMContext):
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 100:
        await message.answer("⚠️ Илтимос, тўғри нарх киритинг:")
        return

    await state.update_data(qoy_narx=int(val))
    await state.set_state(CalcStates.qoy_qozi_narx)
    await message.answer(
        "3️⃣ *1 та қўзининг сотилиш нархини* киритинг (сўм):\n"
        "_(масалан: 1 200 000)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(CalcStates.qoy_qozi_narx)
async def qoy_qozi_process(message: types.Message, state: FSMContext):
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 100:
        await message.answer("⚠️ Илтимос, тўғри нарх киритинг:")
        return

    await state.update_data(qoy_qozi_narx=int(val))
    await state.set_state(CalcStates.qoy_em_narx)
    await message.answer(
        "4️⃣ *Концентрат ем нархини* киритинг (1 кг, сўм):\n"
        "_(масалан: 4 000)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(CalcStates.qoy_em_narx)
async def qoy_em_process(message: types.Message, state: FSMContext):
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Илтимос, ем нархини тўғри кўрсатинг:")
        return

    data = await state.get_data()
    ona = data.get("qoy_bosh")
    narx = data.get("qoy_narx")
    qozi = data.get("qoy_qozi_narx")
    em = int(val)

    try:
        natija = qoy_hisobla(ona, narx, qozi, em)
        await message.answer(
            natija,
            parse_mode="Markdown",
            reply_markup=calc_menu_keyboard()
        )
        await state.set_state(CalcStates.menu)
    except Exception as e:
        logging.error(f"Қўй калькулятори хатоси: {e}")
        await message.answer(f"⚠️ Ҳисоблашда хатолик юз берди:\n{e}")


# ═══════════════════════════════════════
# 🐄 ҚОРАМОЛ КАЛЬКУЛЯТОРИ
# ═══════════════════════════════════════

@router.message(CalcStates.menu, F.text == "🐄 Қорамол калькулятори")
async def qoramol_start(message: types.Message, state: FSMContext):
    await state.set_state(CalcStates.qm_bosh)
    await message.answer(
        "🐄 *Қорамол фермаси калькулятори*\n\n"
        "1️⃣ *Сигирлар (она моллар) сонини* киритинг:\n_(масалан: 10)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(CalcStates.qm_bosh)
async def qm_bosh_process(message: types.Message, state: FSMContext):
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Илтимос, сонини тўғри рақамда киритинг:")
        return

    await state.update_data(qm_bosh=int(val))
    await state.set_state(CalcStates.qm_yon)
    await message.answer(
        "2️⃣ *Йўналишни танланг:*",
        reply_markup=calc_qoramol_direction_keyboard()
    )


@router.message(CalcStates.qm_yon)
async def qm_yon_process(message: types.Message, state: FSMContext):
    if message.text not in ["🥛 Сут", "🥩 Гўшт"]:
        await message.answer("⚠️ Илтимос, пастки тугмалардан бирини танланг:")
        return

    direction = "sut" if "Сут" in message.text else "gosht"
    await state.update_data(qm_yon=direction)
    await state.set_state(CalcStates.qm_sut_vazn)

    if direction == "sut":
        await message.answer(
            "3️⃣ *1 та сигирнинг кунлик сут миқдорини* киритинг (литр):\n"
            "_(масалан: 15)_",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
    else:
        await message.answer(
            "3️⃣ *1 та молнинг ўртача тирик вазнини* киритинг (кг):\n"
            "_(семиртириб сотиш вазни, масалан: 400)_",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )


@router.message(CalcStates.qm_sut_vazn)
async def qm_sut_vazn_process(message: types.Message, state: FSMContext):
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ ХАТО. Тўғри қиймат киритинг:")
        return

    await state.update_data(qm_sut_vazn=int(val))
    await state.set_state(CalcStates.qm_narx)

    data = await state.get_data()
    if data.get("qm_yon") == "sut":
        await message.answer(
            "4️⃣ *1 литр сут сотилиш нархини* киритинг (сўм):\n"
            "_(масалан: 4 500)_",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
    else:
        await message.answer(
            "4️⃣ *1 кг тирик вазн нархини* киритинг (сўм):\n"
            "_(масалан: 25 000)_",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )


@router.message(CalcStates.qm_narx)
async def qm_narx_process(message: types.Message, state: FSMContext):
    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 100:
        await message.answer("⚠️ Тўғри нарх киритинг:")
        return

    await state.update_data(qm_narx=int(val))
    await state.set_state(CalcStates.qm_em_narx)
    await message.answer(
        "5️⃣ *Комбикорм (ем) ўртача нархини* киритинг (1 кг, сўм):\n"
        "_(масалан: 5 000)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(CalcStates.qm_em_narx)
async def qm_em_process(message: types.Message, state: FSMContext):
    data = await state.get_data()
    direction = data.get("qm_yon")

    val = message.text.replace(" ", "")
    if not val.isdigit() or int(val) < 1:
        await message.answer("⚠️ Тўғри ем нархини киритинг:")
        return

    bosh = data.get("qm_bosh")
    sut_vazn = data.get("qm_sut_vazn")
    narx = data.get("qm_narx")
    em = int(val)

    try:
        if direction == "sut":
            natija = qm_hisobla_sut(bosh, sut_vazn, narx, em)
        else:
            natija = qm_hisobla_gosht(bosh, sut_vazn, narx, em)

        await message.answer(
            natija,
            parse_mode="Markdown",
            reply_markup=calc_menu_keyboard()
        )
        await state.set_state(CalcStates.menu)

    except Exception as e:
        logging.error(f"Қорамол калькулятори хатоси: {e}")
        await message.answer(f"⚠️ Ҳисоблашда хатолик юз берди:\n{e}")
