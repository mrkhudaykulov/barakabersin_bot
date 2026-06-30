import html as html_module
import logging

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from config import bot, ADMINS
from states import VetStates, VetSuggestStates
from keyboards import (
    main_menu, main_menu_admin, regions_keyboard, districts_keyboard, DISTRICTS,
    vet_contact_result_keyboard, vet_action_type_keyboard,
    vet_role_type_keyboard, standard_step_keyboard,
    vet_comment_keyboard, vet_confirm_keyboard
)
from database import (
    fix_keyboard_text, add_vet_suggestion, get_approved_vet_override
)
from vet_contacts_data import VET_REGIONS, VET_DISTRICTS

router = Router()

# Расмий маълумотлар манбаи — ҳар бир туман контакт хабарининг бошида кўрсатилади
VET_SOURCE_LINK = "https://gov.uz/uz/vetgov"
VET_SOURCE_LINE = f'ℹ️ Манба: <a href="{VET_SOURCE_LINK}">gov.uz/uz/vetgov</a>\n\n'


def _user_menu(user_id: int):
    """Фойдаланувчи турига қараб тегишли бош менюни қайтаради."""
    return main_menu_admin() if user_id in ADMINS else main_menu()


@router.message(F.text == "🩺 Ветеринария")
async def vet_start(message: types.Message, state: FSMContext):
    await state.set_state(VetStates.region)
    await message.answer(
        "🩺 *Ветеринария хизмати*\n\n"
        "Ҳудудингиздаги ветеринария мутахассиси контактини олиш учун "
        "вилоятни танланг:",
        parse_mode="Markdown",
        reply_markup=regions_keyboard()
    )


@router.message(VetStates.region)
async def vet_region(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return

    fixed = fix_keyboard_text(message.text)
    if fixed not in DISTRICTS:
        await message.answer(
            "⚠️ Илтимос, тугмалардан бирини танланг:",
            reply_markup=regions_keyboard()
        )
        return

    await state.update_data(vet_region=fixed)
    await state.set_state(VetStates.district)
    await message.answer(
        "📍 Туманни танланг:",
        reply_markup=districts_keyboard(fixed)
    )


@router.message(VetStates.district, F.text == "📝 Маълумотга таклиф киритиш")
async def vet_suggest_start(message: types.Message, state: FSMContext):
    """Кўрсатилган туман контактига таклиф киритишни бошлайди."""
    await state.set_state(VetSuggestStates.action_type)
    await message.answer(
        "📝 *Таклиф киритиш*\n\n"
        "Сиз нима қилмоқчисиз?",
        parse_mode="Markdown",
        reply_markup=vet_action_type_keyboard()
    )


@router.message(VetStates.district)
async def vet_district(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш", "📝 Маълумотга таклиф киритиш"]:
        return

    data = await state.get_data()
    region = data.get("vet_region")
    fixed_district = fix_keyboard_text(message.text)

    key = (region, fixed_district)
    info = VET_DISTRICTS.get(key)

    if not info:
        await message.answer(
            "⚠️ Бу туман учун маълумот топилмади. Илтимос, рўйхатдан туман танланг:",
            reply_markup=districts_keyboard(region)
        )
        return

    region_info = VET_REGIONS.get(region)

    # ═══ Тошкент шаҳар (Пойтахт) — кўп туман/бозор рўйхати ═══
    if "bolim_boshligi_list" in info:
        text = (
            f"🩺 <b>Ветеринария хизмати — {html_module.escape(region)} (Пойтахт)</b>\n\n"
            f"{VET_SOURCE_LINE}"
        )

        if region_info:
            text += (
                f"🏛 <b>Вилоят бошқармаси:</b>\n"
                f"   {html_module.escape(region_info['lavozim'])}: "
                f"{html_module.escape(region_info['fish'] or '—')}\n"
                f"   📞 {html_module.escape(region_info['tel'] or '—')}\n\n"
            )

        text += "🏢 <b>Туман бўлим бошлиқлари:</b>\n"
        for item in info["bolim_boshligi_list"]:
            text += (
                f"   📍 {html_module.escape(item['tuman_nomi'])}: "
                f"{html_module.escape(item['fish'] or '—')} "
                f"— 📞 {html_module.escape(item['tel'] or '—')}\n"
            )

        if info["lab_mudiri_list"]:
            text += "\n🔬 <b>Бозор лаборатория мудирлари:</b>\n"
            for item in info["lab_mudiri_list"][:15]:
                text += (
                    f"   🏪 {html_module.escape(item['bozor_nomi'])}: "
                    f"{html_module.escape(item['fish'] or '—')} "
                    f"— 📞 {html_module.escape(item['tel'] or '—')}\n"
                )
            if len(info["lab_mudiri_list"]) > 15:
                text += f"   ... ва яна {len(info['lab_mudiri_list']) - 15} та бозор\n"

        text += (
            f"\n{'─' * 25}\n"
            f"ℹ️ Аниқ бир тумандаги ходим маълумотига таклиф киритиш учун "
            f"вилоятни шу туман номи билан алоҳида танланг."
        )

        await message.answer(text, parse_mode="HTML", reply_markup=_user_menu(message.from_user.id), disable_web_page_preview=True)
        await state.clear()
        return

    # ═══ Оддий туман — биттадан маълумот ═══
    # Тасдиқланган фойдаланувчи таклифлари мавжуд бўлса, статик
    # маълумот ўрнига ўшани кўрсатамиз (энг сўнгги тасдиқланган)
    bolim_override = get_approved_vet_override(region, fixed_district, "bolim_boshligi")
    lab_override = get_approved_vet_override(region, fixed_district, "lab_mudiri")

    bolim = bolim_override or info.get("bolim_boshligi")
    lab = lab_override or info.get("lab_mudiri")

    text = (
        f"🩺 <b>Ветеринария хизмати</b>\n"
        f"📍 {html_module.escape(region)} вилояти, "
        f"{html_module.escape(fixed_district)} тумани\n\n"
        f"{VET_SOURCE_LINE}"
    )

    if bolim:
        text += (
            f"🏢 <b>Туман бўлим бошлиғи:</b>\n"
            f"   👤 {html_module.escape(bolim['fish'] or '—')}\n"
            f"   📞 {html_module.escape(bolim['tel'] or '—')}\n\n"
        )

    if lab:
        text += (
            f"🔬 <b>Бозор ветеринария-санитария лабораторияси мудири:</b>\n"
            f"   👤 {html_module.escape(lab['fish'] or '—')}\n"
            f"   📞 {html_module.escape(lab['tel'] or '—')}\n\n"
        )

    if not bolim and not lab:
        text += "❌ Маълумот мавжуд эмас.\n\n"

    if region_info:
        text += (
            f"{'─' * 25}\n"
            f"🏛 <b>Вилоят бошқармаси:</b>\n"
            f"   {html_module.escape(region_info['lavozim'])}: "
            f"{html_module.escape(region_info['fish'] or '—')}\n"
            f"   📞 {html_module.escape(region_info['tel'] or '—')}\n"
        )

    # Кейинги қадамда таклиф формасида керак бўлади, шуни state'да сақлаймиз
    await state.update_data(vet_district=fixed_district)

    await message.answer(text, parse_mode="HTML", reply_markup=vet_contact_result_keyboard(), disable_web_page_preview=True)
    # ДИҚҚАТ: state ҳали тозаланмайди — "📝 Таклиф киритиш" тугмаси
    # шу region/district контекстидан фойдаланиши учун VetStates.district'да қолади


# ═══════════════════════════════════════
# 📝 ФОЙДАЛАНУВЧИ ТАКЛИФИ — ТЎЛИҚ ОҚИМ
# ═══════════════════════════════════════

@router.message(VetSuggestStates.action_type)
async def vet_suggest_action_type(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return

    if message.text == "🆕 Янги ходим қўшиш":
        action_type = "yangi"
    elif message.text == "✏️ Мавжудини ўзгартириш":
        action_type = "ozgartirish"
    else:
        await message.answer(
            "⚠️ Илтимос, тугмалардан бирини танланг:",
            reply_markup=vet_action_type_keyboard()
        )
        return

    await state.update_data(vet_action_type=action_type)
    await state.set_state(VetSuggestStates.role_type)
    await message.answer(
        "Қайси лавозим ҳақида маълумот?",
        reply_markup=vet_role_type_keyboard()
    )


@router.message(VetSuggestStates.role_type)
async def vet_suggest_role_type(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return

    if message.text == "🏢 Бўлим бошлиғи":
        role_type = "bolim_boshligi"
    elif message.text == "🔬 Лаборатория мудири":
        role_type = "lab_mudiri"
    else:
        await message.answer(
            "⚠️ Илтимос, тугмалардан бирини танланг:",
            reply_markup=vet_role_type_keyboard()
        )
        return

    await state.update_data(vet_role_type=role_type)
    await state.set_state(VetSuggestStates.fish)
    await message.answer(
        "👤 Ф.И.Ш ни тўлиқ киритинг:\n_(масалан: Каримов Анвар Раҳимович)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(VetSuggestStates.fish)
async def vet_suggest_fish(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    if len(message.text.strip()) < 5:
        await message.answer("⚠️ Илтимос, тўлиқ исм-шарифни киритинг:")
        return

    await state.update_data(vet_fish=message.text.strip())
    await state.set_state(VetSuggestStates.lavozim)
    await message.answer(
        "💼 Лавозимини киритинг:\n_(масалан: Бўлим бошлиғи)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(VetSuggestStates.lavozim)
async def vet_suggest_lavozim(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    if len(message.text.strip()) < 3:
        await message.answer("⚠️ Илтимос, лавозимни киритинг:")
        return

    await state.update_data(vet_lavozim=message.text.strip())
    await state.set_state(VetSuggestStates.tel)
    await message.answer(
        "📞 Телефон рақамини киритинг:\n_(масалан: 90 123-45-67)_",
        parse_mode="Markdown",
        reply_markup=standard_step_keyboard()
    )


@router.message(VetSuggestStates.tel)
async def vet_suggest_tel(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    if not any(ch.isdigit() for ch in message.text):
        await message.answer("⚠️ Илтимос, телефон рақамини рақамларда киритинг:")
        return

    await state.update_data(vet_tel=message.text.strip())
    await state.set_state(VetSuggestStates.comment)
    await message.answer(
        "💬 Қўшимча изоҳ қолдирасизми? (ихтиёрий)",
        reply_markup=vet_comment_keyboard()
    )


@router.message(VetSuggestStates.comment)
async def vet_suggest_comment(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return

    if message.text == "⏭ Изоҳсиз ўтказиб юбориш":
        await state.update_data(vet_comment=None)
    else:
        await state.update_data(vet_comment=message.text.strip())

    data = await state.get_data()
    action_text = "🆕 Янги ходим қўшиш" if data["vet_action_type"] == "yangi" else "✏️ Мавжудини ўзгартириш"
    role_text = "Бўлим бошлиғи" if data["vet_role_type"] == "bolim_boshligi" else "Лаборатория мудири"

    summary = (
        f"📝 <b>Таклифингизни текширинг:</b>\n\n"
        f"📍 <b>Ҳудуд:</b> {html_module.escape(data['vet_region'])}, "
        f"{html_module.escape(data['vet_district'])}\n"
        f"🔧 <b>Амал:</b> {action_text}\n"
        f"💼 <b>Лавозим:</b> {role_text}\n"
        f"👤 <b>Ф.И.Ш:</b> {html_module.escape(data['vet_fish'])}\n"
        f"💼 <b>Лавозим номи:</b> {html_module.escape(data['vet_lavozim'])}\n"
        f"📞 <b>Тел:</b> {html_module.escape(data['vet_tel'])}\n"
    )
    if data.get("vet_comment"):
        summary += f"💬 <b>Изоҳ:</b> {html_module.escape(data['vet_comment'])}\n"

    summary += (
        f"\n{'─' * 25}\n"
        f"ℹ️ Таклифингиз админ томонидан кўриб чиқилгандан сўнг "
        f"рўйхатга қўшилади."
    )

    await state.set_state(VetSuggestStates.confirm)
    await message.answer(summary, parse_mode="HTML", reply_markup=vet_confirm_keyboard())


@router.message(VetSuggestStates.confirm, F.text == "✅ Таклифни юбориш")
async def vet_suggest_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()

    username = f"@{message.from_user.username}" if message.from_user.username else None

    suggestion_id = add_vet_suggestion(
        user_id=message.from_user.id,
        username=username,
        action_type=data["vet_action_type"],
        region=data["vet_region"],
        district=data["vet_district"],
        role_type=data["vet_role_type"],
        fish=data["vet_fish"],
        lavozim=data["vet_lavozim"],
        tel=data["vet_tel"],
        comment=data.get("vet_comment"),
    )

    await message.answer(
        f"✅ <b>Таклифингиз юборилди!</b>\n\n"
        f"🆔 Таклиф рақами: <code>{suggestion_id}</code>\n\n"
        f"Админ кўриб чиқиб, тасдиқлагандан сўнг рўйхатга қўшилади.",
        parse_mode="HTML",
        reply_markup=_user_menu(message.from_user.id)
    )
    await state.clear()

    # Админларга хабарнома
    role_text = "Бўлим бошлиғи" if data["vet_role_type"] == "bolim_boshligi" else "Лаборатория мудири"
    action_text = "Янги қўшиш" if data["vet_action_type"] == "yangi" else "Ўзгартириш"
    admin_text = (
        f"🆕 <b>Янги ветеринария таклифи!</b>\n\n"
        f"🆔 №{suggestion_id}\n"
        f"📍 {html_module.escape(data['vet_region'])}, {html_module.escape(data['vet_district'])}\n"
        f"🔧 {action_text} — {role_text}\n"
        f"👤 {html_module.escape(data['vet_fish'])}\n"
        f"📞 {html_module.escape(data['vet_tel'])}\n\n"
        f"Кўриб чиқиш учун: /vetadmin"
    )
    for admin_id in ADMINS:
        try:
            await bot.send_message(chat_id=admin_id, text=admin_text, parse_mode="HTML")
        except Exception as e:
            logging.warning(f"Админга хабар юборилмади ({admin_id}): {e}")


@router.message(VetSuggestStates.confirm)
async def vet_suggest_confirm_fallback(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return
    await message.answer(
        "⚠️ Илтимос, тугмалардан бирини танланг:",
        reply_markup=vet_confirm_keyboard()
    )
