import html as html_module
import logging

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from config import bot, ADMINS
from states import VetAdminStates
from keyboards import (
    main_menu, main_menu_admin, vet_admin_review_keyboard,
    vet_admin_edit_keyboard, vet_admin_edit_field_keyboard, standard_step_keyboard
)
from database import (
    get_pending_vet_suggestions, get_vet_suggestion_by_id,
    review_vet_suggestion, count_pending_vet_suggestions,
    get_approved_vet_override, update_vet_suggestion_fields
)
from vet_contacts_data import VET_DISTRICTS

router = Router()
router.message.filter(F.chat.type == "private")

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


async def _get_current_data(region, district, role_type):
    """
    Ушбу туман/лавозим учун ҲОЗИРГИ (амалдаги) маълумотни қайтаради:
    аввал тасдиқланган override, бўлмаса статик vet_contacts_data.
    Топилмаса None.
    """
    override = await get_approved_vet_override(region, district, role_type)
    if override:
        return override

    info = VET_DISTRICTS.get((region, district))
    if not info:
        return None

    if role_type == "bolim_boshligi":
        # Пойтахт учун рўйхат, оддий туман учун битта объект
        if "bolim_boshligi" in info:
            b = info["bolim_boshligi"]
            return {"fish": b.get("fish"), "lavozim": "Бўлим бошлиғи", "tel": b.get("tel")}
        return None
    else:  # lab_mudiri
        labs = info.get("lab_mudiri_list", [])
        if labs:
            l = labs[0]
            return {"fish": l.get("fish"), "lavozim": "Лаборатория мудири", "tel": l.get("tel")}
        return None


async def _format_suggestion(row) -> str:
    """Кутилаётган таклифни, ўзгартириш бўлса эски маълумот билан солиштириб форматлайди."""
    (sid, user_id, username, action_type, region, district,
     role_type, fish, lavozim, tel, comment, created_at) = row

    action_text = "🆕 Янги ходим қўшиш" if action_type == "yangi" else "✏️ Мавжудини ўзгартириш"
    role_text = "Бўлим бошлиғи" if role_type == "bolim_boshligi" else "Лаборатория мудири"
    uname = username or f"ID: {user_id}"

    text = (
        f"📋 <b>Таклиф №{sid}</b>\n\n"
        f"👤 Юборувчи: {html_module.escape(str(uname))}\n"
        f"📍 <b>Ҳудуд:</b> {html_module.escape(region)}, {html_module.escape(district)}\n"
        f"🔧 <b>Амал:</b> {action_text}\n"
        f"💼 <b>Лавозим тури:</b> {role_text}\n"
    )

    # Агар ЎЗГАРТИРИШ таклифи бўлса — эски маълумотни ёнма-ён кўрсатамиз
    if action_type == "ozgartirish":
        old = await _get_current_data(region, district, role_type)
        text += f"\n{'─' * 25}\n"
        if old:
            text += (
                f"📜 <b>ЭСКИ (амалдаги) маълумот:</b>\n"
                f"   👤 {html_module.escape(old.get('fish') or '—')}\n"
                f"   📞 {html_module.escape(old.get('tel') or '—')}\n"
            )
        else:
            text += "📜 <b>ЭСКИ маълумот:</b> топилмади\n"
        text += (
            f"\n🆕 <b>ЯНГИ (таклиф этилган):</b>\n"
            f"   👤 {html_module.escape(fish or '—')}\n"
            f"   💼 {html_module.escape(lavozim or '—')}\n"
            f"   📞 {html_module.escape(tel or '—')}\n"
        )
    else:
        text += (
            f"\n👤 <b>Ф.И.Ш:</b> {html_module.escape(fish or '—')}\n"
            f"💼 <b>Лавозим номи:</b> {html_module.escape(lavozim or '—')}\n"
            f"📞 <b>Тел:</b> {html_module.escape(tel or '—')}\n"
        )

    if comment:
        text += f"\n💬 <b>Изоҳ:</b> {html_module.escape(comment)}\n"

    return text


async def _show_next_pending(message: types.Message, state: FSMContext):
    """Навбатдаги кутилаётган таклифни кўрсатади."""
    pending = await get_pending_vet_suggestions(limit=1)
    if not pending:
        await message.answer(
            "✅ Кутилаётган таклифлар йўқ.",
            reply_markup=main_menu_admin()
        )
        await state.clear()
        return

    row = pending[0]
    sid = row[0]
    await state.update_data(current_suggestion_id=sid)
    await state.set_state(VetAdminStates.reviewing)

    text = await _format_suggestion(row)
    await message.answer(text, parse_mode="HTML", reply_markup=vet_admin_review_keyboard())


# ═══════════════════════════════════════
# КИРИШ — /vetadmin буйруғи ЁКИ "🩺 Вет таклифлар" тугмаси
# ═══════════════════════════════════════

@router.message(Command("vetadmin"))
@router.message(F.text == "🩺 Вет таклифлар")
async def vet_admin_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    count = await count_pending_vet_suggestions()
    if count == 0:
        await message.answer(
            "✅ Ҳозирда кутилаётган ветеринария таклифлари йўқ.",
            reply_markup=main_menu_admin()
        )
        return

    await message.answer(f"📋 Кутилаётган таклифлар: <b>{count}</b> та", parse_mode="HTML")
    await _show_next_pending(message, state)


# ═══════════════════════════════════════
# ТАСДИҚЛАШ
# ═══════════════════════════════════════

@router.message(VetAdminStates.reviewing, F.text == "✅ Тасдиқлаш")
async def vet_admin_approve(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    sid = data.get("current_suggestion_id")
    if not sid:
        await _show_next_pending(message, state)
        return

    row = await get_vet_suggestion_by_id(sid)
    if not row:
        await message.answer("⚠️ Таклиф топилмади ёки аллақачон кўриб чиқилган.")
        await _show_next_pending(message, state)
        return

    requester_id = row[1]
    await review_vet_suggestion(sid, admin_id=message.from_user.id, approve=True)
    await message.answer(f"✅ Таклиф №{sid} тасдиқланди.")

    try:
        await bot.send_message(
            chat_id=requester_id,
            text=(
                f"✅ <b>Таклифингиз тасдиқланди!</b>\n\n"
                f"Сиз юборган ветеринария маълумоти энди рўйхатда кўринади. Раҳмат!"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Фойдаланувчига хабар юборилмади ({requester_id}): {e}")

    await _show_next_pending(message, state)


# ═══════════════════════════════════════
# РАД ЭТИШ
# ═══════════════════════════════════════

@router.message(VetAdminStates.reviewing, F.text == "❌ Рад этиш")
async def vet_admin_reject_ask(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(VetAdminStates.reject_comment)
    await message.answer(
        "❌ Рад этиш сабабини ёзинг (ёки '-' деб ёзинг сабабсиз рад этиш учун):",
        reply_markup=standard_step_keyboard()
    )


@router.message(VetAdminStates.reject_comment)
async def vet_admin_reject_confirm(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.set_state(VetAdminStates.reviewing)
        await _show_next_pending(message, state)
        return

    data = await state.get_data()
    sid = data.get("current_suggestion_id")
    if not sid:
        await _show_next_pending(message, state)
        return

    row = await get_vet_suggestion_by_id(sid)
    if not row:
        await message.answer("⚠️ Таклиф топилмади.")
        await _show_next_pending(message, state)
        return

    requester_id = row[1]
    reason = None if message.text.strip() == "-" else message.text.strip()
    await review_vet_suggestion(sid, admin_id=message.from_user.id, approve=False, admin_comment=reason)
    await message.answer(f"❌ Таклиф №{sid} рад этилди.")

    try:
        notify_text = f"❌ <b>Таклифингиз рад этилди.</b>\n\nТаклиф №{sid}"
        if reason:
            notify_text += f"\n\n💬 Сабаб: {html_module.escape(reason)}"
        await bot.send_message(chat_id=requester_id, text=notify_text, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"Фойдаланувчига хабар юборилмади ({requester_id}): {e}")

    await _show_next_pending(message, state)


# ═══════════════════════════════════════
# ТАҲРИРЛАШ (янги ва ўзгартириш таклифлари учун)
# ═══════════════════════════════════════

@router.message(VetAdminStates.reviewing, F.text == "✏️ Таҳрирлаш")
async def vet_admin_edit_menu(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    sid = data.get("current_suggestion_id")
    row = await get_vet_suggestion_by_id(sid) if sid else None
    if not row:
        await message.answer("⚠️ Таклиф топилмади.")
        await _show_next_pending(message, state)
        return

    fish, lavozim, tel = row[7], row[8], row[9]
    text = (
        f"✏️ <b>Таклиф №{sid} — таҳрирлаш</b>\n\n"
        f"Жорий қийматлар:\n"
        f"   👤 Ф.И.Ш: {html_module.escape(fish or '—')}\n"
        f"   💼 Лавозим: {html_module.escape(lavozim or '—')}\n"
        f"   📞 Телефон: {html_module.escape(tel or '—')}\n\n"
        f"Қайси майдонни ўзгартирасиз?"
    )
    await state.set_state(VetAdminStates.reviewing)
    await message.answer(text, parse_mode="HTML", reply_markup=vet_admin_edit_keyboard())


@router.message(VetAdminStates.reviewing, F.text == "👤 Ф.И.Ш")
async def vet_admin_edit_fish_ask(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(VetAdminStates.edit_fish)
    await message.answer("👤 Янги Ф.И.Ш ни киритинг:", reply_markup=vet_admin_edit_field_keyboard())


@router.message(VetAdminStates.edit_fish)
async def vet_admin_edit_fish_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text == "🔙 Орқага":
        await state.set_state(VetAdminStates.reviewing)
        await message.answer("Таҳрирлашга қайтдингиз:", reply_markup=vet_admin_edit_keyboard())
        return

    data = await state.get_data()
    sid = data.get("current_suggestion_id")
    await update_vet_suggestion_fields(sid, fish=message.text.strip())
    await state.set_state(VetAdminStates.reviewing)
    await message.answer("✅ Ф.И.Ш янгиланди.", reply_markup=vet_admin_edit_keyboard())


@router.message(VetAdminStates.reviewing, F.text == "💼 Лавозим")
async def vet_admin_edit_lavozim_ask(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(VetAdminStates.edit_lavozim)
    await message.answer("💼 Янги лавозим номини киритинг:", reply_markup=vet_admin_edit_field_keyboard())


@router.message(VetAdminStates.edit_lavozim)
async def vet_admin_edit_lavozim_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text == "🔙 Орқага":
        await state.set_state(VetAdminStates.reviewing)
        await message.answer("Таҳрирлашга қайтдингиз:", reply_markup=vet_admin_edit_keyboard())
        return

    data = await state.get_data()
    sid = data.get("current_suggestion_id")
    await update_vet_suggestion_fields(sid, lavozim=message.text.strip())
    await state.set_state(VetAdminStates.reviewing)
    await message.answer("✅ Лавозим янгиланди.", reply_markup=vet_admin_edit_keyboard())


@router.message(VetAdminStates.reviewing, F.text == "📞 Телефон")
async def vet_admin_edit_tel_ask(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(VetAdminStates.edit_tel)
    await message.answer("📞 Янги телефон рақамини киритинг:", reply_markup=vet_admin_edit_field_keyboard())


@router.message(VetAdminStates.edit_tel)
async def vet_admin_edit_tel_save(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text == "🔙 Орқага":
        await state.set_state(VetAdminStates.reviewing)
        await message.answer("Таҳрирлашга қайтдингиз:", reply_markup=vet_admin_edit_keyboard())
        return

    data = await state.get_data()
    sid = data.get("current_suggestion_id")
    await update_vet_suggestion_fields(sid, tel=message.text.strip())
    await state.set_state(VetAdminStates.reviewing)
    await message.answer("✅ Телефон янгиланди.", reply_markup=vet_admin_edit_keyboard())


@router.message(VetAdminStates.reviewing, F.text == "✅ Таҳрирни сақлаш")
async def vet_admin_edit_done(message: types.Message, state: FSMContext):
    """Таҳрирдан сўнг янгиланган таклифни қайта кўрсатади."""
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    sid = data.get("current_suggestion_id")
    row = await get_vet_suggestion_by_id(sid) if sid else None
    if not row:
        await _show_next_pending(message, state)
        return
    await message.answer("✅ Таҳрир сақланди. Янгиланган таклиф:")
    text = await _format_suggestion(row)
    await message.answer(text, parse_mode="HTML", reply_markup=vet_admin_review_keyboard())


@router.message(VetAdminStates.reviewing, F.text == "🔙 Орқага")
async def vet_admin_edit_back(message: types.Message, state: FSMContext):
    """Таҳрирлаш менюсидан кўриб чиқишга қайтиш."""
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    sid = data.get("current_suggestion_id")
    row = await get_vet_suggestion_by_id(sid) if sid else None
    if not row:
        await _show_next_pending(message, state)
        return
    text = await _format_suggestion(row)
    await message.answer(text, parse_mode="HTML", reply_markup=vet_admin_review_keyboard())


# ═══════════════════════════════════════
# КЕЙИНГИСИГА ЎТИШ
# ═══════════════════════════════════════

@router.message(VetAdminStates.reviewing, F.text == "⏭ Кейингисига ўтиш")
async def vet_admin_skip(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    pending = await get_pending_vet_suggestions(limit=2)
    if len(pending) <= 1:
        await message.answer("ℹ️ Бошқа кутилаётган таклиф йўқ.", reply_markup=main_menu_admin())
        await state.clear()
        return

    row = pending[1]
    sid = row[0]
    await state.update_data(current_suggestion_id=sid)
    text = await _format_suggestion(row)
    await message.answer(text, parse_mode="HTML", reply_markup=vet_admin_review_keyboard())
