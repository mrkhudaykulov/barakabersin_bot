import logging
import sqlite3

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from keyboards import (
    notify_menu_keyboard, notification_districts_keyboard,
    main_menu, main_menu_admin, calc_menu_keyboard, standard_step_keyboard,
    calc_qoramol_direction_keyboard, photo_confirm_keyboard,
    animal_types_keyboard, regions_keyboard, districts_keyboard,
    description_keyboard, search_animal_keyboard,
    admin_menu_keyboard, admin_ads_keyboard,
    admin_prices_keyboard, admin_block_keyboard, admin_premium_keyboard
)
from states import AdStates, CalcStates, SearchStates, PriceInputStates, NotifyStates, AdminStates
from database import get_connection, get_placeholder, save_user
from config import ADMINS

router = Router()


@router.message(Command("start"))
async def start_cmd(message: types.Message):
    save_user(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username
    )
    # ═══ АДМИН ТЕКШИРИШ ═══
    if message.from_user.id in ADMINS:
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="➕ Эълон бериш"), KeyboardButton(text="🔍 Эълон қидириш")],
            [KeyboardButton(text="📊 Нархлар индекси"), KeyboardButton(text="🗂 Менинг эълонларим")],
            [KeyboardButton(text="🧮 Ферма калькулятори"), KeyboardButton(text="🔔 Хабардор қил")],
            [KeyboardButton(text="🔐 Админ панел")]
        ], resize_keyboard=True)
    else:
        kb = main_menu()

    await message.answer(
        "Ассалому алайкум! Чорва бозор ботига хуш келибсиз. Керакли бўлимни менюдаги тугмаларда танланг!",
        reply_markup=kb
    )


@router.message(F.text == "🏠 Бош меню")
async def home_menu(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id in ADMINS:
        from keyboards import main_menu_admin
        await message.answer("🏠 Асосий меню", reply_markup=main_menu_admin())
    else:
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

    await state.clear()
    if message.from_user.id in ADMINS:
        await message.answer("❌ Жараён бекор қилинди.", reply_markup=main_menu_admin())
    else:
        await message.answer("❌ Жараён бекор қилинди.", reply_markup=main_menu())


@router.message(F.text == "🔙 Орқага")
async def global_back_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        if message.from_user.id in ADMINS:
            await message.answer("❌ Фаол жараён мавжуд эмас.", reply_markup=main_menu_admin())
        else:
            await message.answer("❌ Фаол жараён мавжуд эмас.", reply_markup=main_menu())
        return

    # ═══ АДМИН ПАНЕЛ — ЯНГИ БЛОК ═══
    if current_state and current_state.startswith("AdminStates"):
        if current_state in [
            AdminStates.ads_menu.state,
            AdminStates.prices_menu.state,
            AdminStates.block_menu.state,
            AdminStates.premium_menu.state,
        ]:
            await state.set_state(AdminStates.menu)
            await message.answer("🔐 Админ панел", reply_markup=admin_menu_keyboard())
            return

        elif current_state in [
            AdminStates.add_price_animal.state,
            AdminStates.add_price_region.state,
            AdminStates.add_price_value.state,
            AdminStates.add_multi_text.state,
            AdminStates.del_price_id.state,
            AdminStates.del_animal_name.state,
            AdminStates.del_region_name.state,
        ]:
            await state.set_state(AdminStates.prices_menu)
            await message.answer("💰 Нархлар бошқариши", reply_markup=admin_prices_keyboard())
            return

        elif current_state in [
            AdminStates.del_ad_id.state,
            AdminStates.del_user_ads_id.state,
        ]:
            await state.set_state(AdminStates.ads_menu)
            await message.answer("📋 Эълонлар бошқариши", reply_markup=admin_ads_keyboard())
            return

        elif current_state == AdminStates.unblock_id.state:
            await state.set_state(AdminStates.block_menu)
            await message.answer("🚫 Блок бошқариши", reply_markup=admin_block_keyboard())
            return

        elif current_state in [
            AdminStates.premium_give_id.state,
            AdminStates.premium_remove_id.state,
        ]:
            await state.set_state(AdminStates.premium_menu)
            await message.answer("💎 Премиум бошқариши", reply_markup=admin_premium_keyboard())
            return

        elif current_state == AdminStates.broadcast_text.state:
            await state.set_state(AdminStates.menu)
            await message.answer("🔐 Админ панел", reply_markup=admin_menu_keyboard())
            return

        else:
            await state.clear()
            if message.from_user.id in ADMINS:
                await message.answer("🏠 Асосий меню", reply_markup=main_menu_admin())
            else:
                await message.answer("🏠 Асосий меню", reply_markup=main_menu())
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


# ═══ Хабарнома (Notify) ═══
    elif current_state == NotifyStates.animal_type.state:
        await state.clear()
        await message.answer("🏠 Асосий меню", reply_markup=main_menu())
        return

    elif current_state == NotifyStates.region.state:
        await state.set_state(NotifyStates.animal_type)
        await message.answer(
            "Қайси чорва ҳақида хабардор қилиш керак?",
            reply_markup=search_animal_keyboard()
        )
        return

    elif current_state == NotifyStates.district.state:
        await state.set_state(NotifyStates.region)
        await message.answer("Қайси вилоят бўйича?", reply_markup=regions_keyboard())
        return

    elif current_state == NotifyStates.min_price.state:
        data = await state.get_data()
        region = data.get("region", "Тошкент")
        await state.set_state(NotifyStates.district)
        await message.answer(
            "🏘 Қайси туманда қидирилади?\n\nЁки, *📍 Барчаси* тугмасини танланг.",
            parse_mode="Markdown",
            reply_markup=notification_districts_keyboard(region)
        )
        return

    elif current_state == NotifyStates.max_price.state:
        await state.set_state(NotifyStates.min_price)
        await message.answer(
            "Минимал (энг паст) нархи қанча бўлсин?",
            reply_markup=standard_step_keyboard()
        )
        return

    elif current_state == NotifyStates.edit_min_price.state:
        await state.clear()
        await message.answer("❌ Таҳрирлаш бекор қилинди.", reply_markup=notify_menu_keyboard())
        return

    elif current_state == NotifyStates.edit_max_price.state:
        await state.set_state(NotifyStates.edit_min_price)
        await message.answer(
            "✏️ Янги *минимал нархни* киритинг:",
            parse_mode="Markdown",
            reply_markup=standard_step_keyboard()
        )
        return
