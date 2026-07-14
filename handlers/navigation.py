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
    admin_prices_keyboard, admin_block_keyboard, admin_premium_keyboard,
    vet_contact_result_keyboard, vet_action_type_keyboard, vet_role_type_keyboard,
    vet_comment_keyboard, market_analysis_menu, price_index_keyboard,
    phone_keyboard
)
from states import (
    AdStates, CalcStates, SearchStates, PriceInputStates, NotifyStates,
    AdminStates, VetStates, VetSuggestStates, MarketStates, PriceIndexStates,
    OnboardingStates
)
from database import get_connection, get_placeholder, save_user, get_user_profile, fix_keyboard_text
from config import ADMINS

router = Router()
router.message.filter(F.chat.type == "private")  # гуруҳларда мену/кнопкалар КЎРИНМАСИН

def _get_home_kb(user_id: int):
    """Фойдаланувчи турига мос бош меню клавиатураси."""
    return main_menu_admin() if user_id in ADMINS else main_menu()


async def _add_group_admin_buttons_if_any(kb, user_id: int):
    """
    Агар фойдаланувчи биror боғланган гуруҳда (ҳақиқий Telegram админи
    сифатида) бўлса — "Менинг гуруҳларим"/"Мен блокладим" тугмаларини
    мавжуд клавиатурага қўшиб қайтаради. Бош ADMINS'га ҳам, оддий
    фойдаланувчиларга ҳам бир xil tarzda ishlaydi.
    """
    try:
        from groups import get_user_managed_groups
        managed = await get_user_managed_groups(user_id)
    except Exception:
        managed = []
    if managed:
        kb.keyboard.append([
            KeyboardButton(text="🏘 Менинг гуруҳларим"),
            KeyboardButton(text="🚫 Мен блокладим"),
        ])
    return kb

def _get_ads_show_profile_summary():
    """Айланма импортни олдини олиш учун lazy import."""
    from ads import _show_profile_summary
    return _show_profile_summary

async def _ask_next_onboarding_step(message: types.Message, state: FSMContext):
    """
    Профилда етишмаган биринчи майдонни сўрайди.
    Ҳаммаси тўлдирилган бўлса — онбординг тугайди, бош меню кўрсатилади.
    """
    profile = await get_user_profile(message.from_user.id)
 
    if not profile.get("region"):
        await state.set_state(OnboardingStates.region)
        await message.answer(
            "📍 Аввал бир марта қисқа маълумот сўраймиз — бу кейинги "
            "эълонларингизда автоматик тўлдирилади.\n\n"
            "Вилоятингизни танланг:",
            reply_markup=regions_keyboard()
        )
        return
 
    if not profile.get("district"):
        await state.set_state(OnboardingStates.district)
        await message.answer(
            "🏘 Туманингизни танланг:",
            reply_markup=districts_keyboard(profile["region"])
        )
        return
 
    if not profile.get("mfy"):
        await state.set_state(OnboardingStates.mfy)
        await message.answer(
            "🏡 МФЙ номингизни ёзинг (матн кўринишида):",
            reply_markup=standard_step_keyboard()
        )
        return
 
    if not profile.get("phone"):
        await state.set_state(OnboardingStates.phone)
        await message.answer(
            "📞 Алоқа учун телефон рақамингизни юборинг:",
            reply_markup=phone_keyboard()
        )
        return
 
    # Ҳаммаси тўлиқ — онбординг тугади
    await state.clear()
    await message.answer(
        "✅ Раҳмат! Маълумотларингиз сақланди — энди эълон беришда "
        "автоматик тўлдирилади.",
        reply_markup=_get_home_kb(message.from_user.id)
    )
 
 
@router.message(OnboardingStates.region)
async def onboarding_region(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.clear()
        await message.answer("Асосий менюга ўтдингиз. Маълумотингизни "
                              "истаган вақтда эълон беришда тўлдиришингиз мумкин.",
                              reply_markup=_get_home_kb(message.from_user.id))
        return
    fixed = fix_keyboard_text(message.text)
    await save_user(user_id=message.from_user.id, region=fixed)
    await _ask_next_onboarding_step(message, state)
 
 
@router.message(OnboardingStates.district)
async def onboarding_district(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.clear()
        await message.answer("Асосий менюга ўтдингиз.",
                              reply_markup=_get_home_kb(message.from_user.id))
        return
    fixed = fix_keyboard_text(message.text)
    await save_user(user_id=message.from_user.id, district=fixed)
    await _ask_next_onboarding_step(message, state)
 
 
@router.message(OnboardingStates.mfy)
async def onboarding_mfy(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.clear()
        await message.answer("Асосий менюга ўтдингиз.",
                              reply_markup=_get_home_kb(message.from_user.id))
        return
    await save_user(user_id=message.from_user.id, mfy=message.text.strip())
    await _ask_next_onboarding_step(message, state)
 
 
@router.message(OnboardingStates.phone, F.contact | F.text)
async def onboarding_phone(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.clear()
        await message.answer("Асосий менюга ўтдингиз.",
                              reply_markup=_get_home_kb(message.from_user.id))
        return
 
    phone = message.contact.phone_number if message.contact else message.text
    if not any(ch.isdigit() for ch in phone):
        await message.answer("⚠️ Илтимос, телефон рақамини тўғри форматда юборинг.")
        return
 
    await save_user(user_id=message.from_user.id, phone=phone)
    await _ask_next_onboarding_step(message, state)
 


@router.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await save_user(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username
    )

    await message.answer(
        "Ассалому алайкум! Чорва бозор ботига хуш келибсиз!"
    )

    # ═══ ПРОФИЛ ТЎЛИҚМИ? Бўлмаса — онбординг ═══
    profile = await get_user_profile(message.from_user.id)
    if not (profile.get("region") and profile.get("district") and profile.get("phone")):
        await _ask_next_onboarding_step(message, state)
        return

    kb = _get_home_kb(message.from_user.id)
    kb = await _add_group_admin_buttons_if_any(kb, message.from_user.id)
    await message.answer(
        "Керакли бўлимни менюдаги тугмаларда танланг!",
        reply_markup=kb
    )


@router.message(F.text == "🏠 Бош меню")
async def home_menu(message: types.Message, state: FSMContext):
    await state.clear()
    kb = _get_home_kb(message.from_user.id)
    kb = await _add_group_admin_buttons_if_any(kb, message.from_user.id)
    await message.answer("🏠 Асосий меню", reply_markup=kb)


@router.message(F.text == "📊 Бозор таҳлили")
async def market_analysis_start(message: types.Message, state: FSMContext):
    await state.set_state(MarketStates.menu)
    await message.answer(
        "📊 *Бозор таҳлили*\n\n"
        "Нархлар индексини кўриш ёки фермер калькуляторидан "
        "фойдаланиш мумкин:",
        parse_mode="Markdown",
        reply_markup=market_analysis_menu()
    )

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

    # ═══ Бозор таҳлили субменюси ═══
    elif current_state == CalcStates.menu.state:
        await state.set_state(MarketStates.menu)
        await message.answer(
            "📊 Бозор таҳлили бўлимига қайтдингиз:",
            reply_markup=market_analysis_menu()
        )
        return

    elif current_state == PriceIndexStates.menu.state:
        await state.set_state(MarketStates.menu)
        await message.answer(
            "📊 Бозор таҳлили бўлимига қайтдингиз:",
            reply_markup=market_analysis_menu()
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
        data = await state.get_data()
        if data.get("editing_profile"):
            await state.update_data(editing_profile=False)
            show_summary = _get_ads_show_profile_summary()
            await show_summary(message, state)
            return
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
        if data.get("editing_profile"):
            await state.update_data(editing_profile=False)
            show_summary = _get_ads_show_profile_summary()
            await show_summary(message, state)
            return
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
        data = await state.get_data()
        if data.get("editing_profile"):
            await state.update_data(editing_profile=False)
            show_summary = _get_ads_show_profile_summary()
            await show_summary(message, state)
            return
        await state.set_state(AdStates.description)
        await message.answer(
            "🔙 Изоҳ бўлимига қайтилди:",
            reply_markup=description_keyboard()
        )
        return

    elif current_state == AdStates.profile_confirm.state:
        # Бу экранда амаллар inline тугмалар орқали бажарилади;
        # эски reply-keyboard'дан келган матн бўлса, summary'ни қайта кўрсатамиз.
        show_summary = _get_ads_show_profile_summary()
        await show_summary(message, state)
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

    # ═══ Ветеринария ═══
    elif current_state == VetStates.region.state:
        await state.clear()
        if message.from_user.id in ADMINS:
            await message.answer("🏠 Асосий меню", reply_markup=main_menu_admin())
        else:
            await message.answer("🏠 Асосий меню", reply_markup=main_menu())
        return

    elif current_state == VetStates.district.state:
        await state.set_state(VetStates.region)
        await message.answer(
            "🔙 Вилоятни қайта танланг:",
            reply_markup=regions_keyboard()
        )
        return

    # ═══ Ветеринария таклифи ═══
    elif current_state == VetSuggestStates.action_type.state:
        await state.set_state(VetStates.district)
        await message.answer(
            "🔙 Контакт маълумотига қайтдингиз:",
            reply_markup=vet_contact_result_keyboard()
        )
        return

    elif current_state == VetSuggestStates.role_type.state:
        await state.set_state(VetSuggestStates.action_type)
        await message.answer(
            "🔙 Амал турини қайта танланг:",
            reply_markup=vet_action_type_keyboard()
        )
        return

    elif current_state == VetSuggestStates.fish.state:
        await state.set_state(VetSuggestStates.role_type)
        await message.answer(
            "🔙 Лавозим турини қайта танланг:",
            reply_markup=vet_role_type_keyboard()
        )
        return

    elif current_state == VetSuggestStates.lavozim.state:
        await state.set_state(VetSuggestStates.fish)
        await message.answer(
            "🔙 Ф.И.Ш ни қайта киритинг:",
            reply_markup=standard_step_keyboard()
        )
        return

    elif current_state == VetSuggestStates.tel.state:
        await state.set_state(VetSuggestStates.lavozim)
        await message.answer(
            "🔙 Лавозим номини қайта киритинг:",
            reply_markup=standard_step_keyboard()
        )
        return

    elif current_state == VetSuggestStates.comment.state:
        await state.set_state(VetSuggestStates.tel)
        await message.answer(
            "🔙 Телефон рақамини қайта киритинг:",
            reply_markup=standard_step_keyboard()
        )
        return

    elif current_state == VetSuggestStates.confirm.state:
        await state.set_state(VetSuggestStates.comment)
        await message.answer(
            "🔙 Изоҳни қайта киритинг:",
            reply_markup=vet_comment_keyboard()
        )
        return
