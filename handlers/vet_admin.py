import html as html_module
import logging

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from config import bot, ADMINS
from states import VetAdminStates
from keyboards import main_menu, main_menu_admin, vet_admin_review_keyboard, standard_step_keyboard
from database import (
    get_pending_vet_suggestions, get_vet_suggestion_by_id,
    review_vet_suggestion, count_pending_vet_suggestions
)

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


def _format_suggestion(row) -> str:
    """Кутилаётган таклифни матн кўринишида форматлайди."""
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
        f"👤 <b>Ф.И.Ш:</b> {html_module.escape(fish or '—')}\n"
        f"💼 <b>Лавозим номи:</b> {html_module.escape(lavozim or '—')}\n"
        f"📞 <b>Тел:</b> {html_module.escape(tel or '—')}\n"
    )
    if comment:
        text += f"💬 <b>Изоҳ:</b> {html_module.escape(comment)}\n"

    return text


async def _show_next_pending(message: types.Message, state: FSMContext):
    """Навбатдаги кутилаётган таклифни кўрсатади, бўлмаса хабар беради."""
    pending = get_pending_vet_suggestions(limit=1)
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

    text = _format_suggestion(row)
    await message.answer(text, parse_mode="HTML", reply_markup=vet_admin_review_keyboard())


@router.message(Command("vetadmin"))
async def vet_admin_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    count = count_pending_vet_suggestions()
    if count == 0:
        await message.answer(
            "✅ Ҳозирда кутилаётган ветеринария таклифлари йўқ.",
            reply_markup=main_menu_admin()
        )
        return

    await message.answer(f"📋 Кутилаётган таклифлар: <b>{count}</b> та", parse_mode="HTML")
    await _show_next_pending(message, state)


@router.message(VetAdminStates.reviewing, F.text == "✅ Тасдиқлаш")
async def vet_admin_approve(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    sid = data.get("current_suggestion_id")
    if not sid:
        await _show_next_pending(message, state)
        return

    row = get_vet_suggestion_by_id(sid)
    if not row:
        await message.answer("⚠️ Таклиф топилмади ёки аллақачон кўриб чиқилган.")
        await _show_next_pending(message, state)
        return

    requester_id = row[1]

    review_vet_suggestion(sid, admin_id=message.from_user.id, approve=True)

    await message.answer(f"✅ Таклиф №{sid} тасдиқланди.")

    try:
        await bot.send_message(
            chat_id=requester_id,
            text=(
                f"✅ <b>Таклифингиз тасдиқланди!</b>\n\n"
                f"Сиз юборган ветеринария маълумоти энди рўйхатда кўринади. "
                f"Раҳмат!"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Фойдаланувчига хабар юборилмади ({requester_id}): {e}")

    await _show_next_pending(message, state)


@router.message(VetAdminStates.reviewing, F.text == "❌ Рад этиш")
async def vet_admin_reject_ask(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(VetAdminStates.reject_comment)
    await message.answer(
        "❌ Рад этиш сабабини ёзинг (ёки '-' деб ёзинг агар сабабсиз рад этмоқчи бўлсангиз):",
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

    row = get_vet_suggestion_by_id(sid)
    if not row:
        await message.answer("⚠️ Таклиф топилмади.")
        await _show_next_pending(message, state)
        return

    requester_id = row[1]
    reason = None if message.text.strip() == "-" else message.text.strip()

    review_vet_suggestion(sid, admin_id=message.from_user.id, approve=False, admin_comment=reason)

    await message.answer(f"❌ Таклиф №{sid} рад этилди.")

    try:
        notify_text = f"❌ <b>Таклифингиз рад этилди.</b>\n\nТаклиф №{sid}"
        if reason:
            notify_text += f"\n\n💬 Сабаб: {html_module.escape(reason)}"
        await bot.send_message(chat_id=requester_id, text=notify_text, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"Фойдаланувчига хабар юборилмади ({requester_id}): {e}")

    await _show_next_pending(message, state)


@router.message(VetAdminStates.reviewing, F.text == "⏭ Кейингисига ўтиш")
async def vet_admin_skip(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    # Ҳозирги таклифни ўтказиб юбориш — кейинги pending'ни кўрсатамиз.
    # Эслатма: бу таклиф ҳолатини ўзгартирмайди, фақат навбатда қолади.
    pending = get_pending_vet_suggestions(limit=2)
    if len(pending) <= 1:
        await message.answer("ℹ️ Бошқа кутилаётган таклиф йўқ.", reply_markup=main_menu_admin())
        await state.clear()
        return

    row = pending[1]
    sid = row[0]
    await state.update_data(current_suggestion_id=sid)
    text = _format_suggestion(row)
    await message.answer(text, parse_mode="HTML", reply_markup=vet_admin_review_keyboard())
