"""
groups.py

Ботни гуруҳга қўшилганда — қайси вилоят(лар)га боғлашни сўрайди.

ТАСДИҚЛАШ ВАКОЛАТИ: Telegram'нинг ЖОНЛИ admin ро'йхатидан эмас, БИЗНИНГ
`group_admins` жадвалидан текширилади. Бот гуруҳга қўшилганда, УНИ
ҚЎШГАН ОДАМ автоматик равишда шу гуруҳ учун ваколатли деб белгиланади.
Бош админ (ADMINS) буни исталган вақтда ўзгартириши/қўшимча одам
қўшиши мумкин: /addgroupadmin ва /removegroupadmin буйруқлари орқали
(гуруҳда, керакли одамнинг хабарига REPLY қилиб).

Эълон яратилганда (ads.py'даги _finalize_ad'дан), шу вилоятга боғланган
барча актив гуруҳларга ✅/❌ тугмали хабар юборилади — КАНАЛДАГИ БИЛАН
БИР ХИЛ форматда (ads.py'даги build_full_ad_caption орқали).
"""

import logging

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from keyboards import DISTRICTS
from database import (
    add_region_group, remove_region_group, deactivate_chat, get_regions_for_chat,
    get_ad_group_post, review_ad_group_post,
    get_all_active_group_chat_ids, get_blocks_by_admin,
    add_group_admin, remove_group_admin, is_group_admin, get_chats_managed_by,
)

router = Router()

REGIONS = list(DISTRICTS.keys())


async def get_user_managed_groups(user_id: int):
    """
    Фойдаланувчи ТАСДИҚЛАШ ВАКОЛАТИГА эга бўлган гуруҳлар — БИЗНИНГ
    group_admins жадвалидан (Telegram API'га мурожаат қилинмайди, тезроқ).
    Қайтаради: [(chat_id, chat_title, regions_list), ...]
    """
    chat_ids = get_chats_managed_by(user_id)
    if not chat_ids:
        return []
    all_groups = get_all_active_group_chat_ids()
    result = []
    for chat_id in chat_ids:
        info = all_groups.get(chat_id)
        if info:
            result.append((chat_id, info["chat_title"], info["regions"]))
    return result


@router.message(F.text == "🏘 Менинг гуруҳларим")
async def my_managed_groups(message: types.Message):
    groups = await get_user_managed_groups(message.from_user.id)
    if not groups:
        await message.answer(
            "ℹ️ Сиз ҳозирча ҳеч қандай боғланган гуруҳ учун тасдиқлаш "
            "ваколатига эга эмассиз."
        )
        return

    text = "🏘 <b>Сиз тасдиқлаш ваколатига эга гуруҳлар:</b>\n\n"
    for chat_id, chat_title, regions in groups:
        text += f"• <b>{chat_title}</b>\n   Вилоят(лар): {', '.join(regions)}\n\n"
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🚫 Мен блокладим")
async def my_blocked_users(message: types.Message):
    blocks = get_blocks_by_admin(message.from_user.id)
    if not blocks:
        await message.answer("ℹ️ Сиз ҳозирча ҳеч кимни блокламагансиз.")
        return

    text = f"🚫 <b>Сиз блоклаган фойдаланувчилар ({len(blocks)} та):</b>\n\n"
    for user_id, ad_id, reason, created_at, full_name, username in blocks[:30]:
        uname = f"@{username}" if username else f"ID:{user_id}"
        text += f"• {full_name or '—'} ({uname})\n   {created_at}\n\n"
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🏘 Уланган гуруҳлар")
async def all_connected_groups(message: types.Message):
    """Фақат бош админлар учун — БАРЧА боғланган гуруҳлар рўйхати."""
    from config import ADMINS
    if message.from_user.id not in ADMINS:
        return

    all_groups = get_all_active_group_chat_ids()
    if not all_groups:
        await message.answer("ℹ️ Ҳозирча ҳеч қандай гуруҳ боғланмаган.")
        return

    text = f"🏘 <b>Уланган гуруҳлар ({len(all_groups)} та):</b>\n\n"
    for chat_id, info in all_groups.items():
        uname = f"@{info['chat_username']}" if info["chat_username"] else "приват"
        text += (
            f"• <b>{info['chat_title']}</b> ({uname})\n"
            f"   Вилоят(лар): {', '.join(info['regions'])}\n\n"
        )
    await message.answer(text, parse_mode="HTML")


def _build_region_inline_kb(selected_regions=None):
    """
    Вилоят танлаш тугмалари. `selected_regions` берилса —
    аллақачон танланганлар олдига ✅ қўшиб кўрсатади (checkmark).
    """
    selected_regions = selected_regions or set()
    buttons = []
    row = []
    for r in REGIONS:
        label = f"✅ {r}" if r in selected_regions else r
        row.append(InlineKeyboardButton(text=label, callback_data=f"reggroup_{r}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="✅ Тугатиш", callback_data="reggroup_done")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ═══════════════════════════════════════
# БОТ ГУРУҲГА ҚЎШИЛДИ / ЧИҚАРИЛДИ
# ═══════════════════════════════════════

@router.my_chat_member()
async def on_bot_membership_changed(event: types.ChatMemberUpdated):
    """
    my_chat_member Telegram'да ФАҚАТ ботнинг ўз ҳолати ўзгарганда келади.
    `event.from_user` — БОТНИ ҚЎШГАН/ЧИҚАРГАН одам.
    """
    if event.chat.type not in ("group", "supergroup"):
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    was_in = old_status in ("member", "administrator", "creator")
    is_in = new_status in ("member", "administrator", "creator")

    if not was_in and is_in:
        # Бот янги қўшилди — ҚЎШГАН ОДАМ автоматик тасдиқловчи бўлади
        add_group_admin(event.chat.id, event.from_user.id, granted_by=None)

        kb = _build_region_inline_kb()
        try:
            await bot.send_message(
                chat_id=event.chat.id,
                text=(
                    "👋 Салом! Ботни ушбу гуруҳга қўшганингиз учун раҳмат.\n\n"
                    f"✅ Сиз ({event.from_user.full_name}) шу гуруҳ учун "
                    f"эълонларни тасдиқлаш ваколатига эга бўлдингиз.\n\n"
                    "Бу гуруҳни қайси вилоят(лар)га боғлаймиз? "
                    "Танланган вилоятдан эълон киритилса, шу гуруҳга ҳам юборилади.\n\n"
                    "(Бир нечта вилоят танлашингиз мумкин)"
                ),
                reply_markup=kb
            )
        except Exception as e:
            logging.warning(f"Гуруҳга (chat_id={event.chat.id}) хабар юборилмади: {e}")

    elif was_in and not is_in:
        # Бот чиқарилди/чиқиб кетди
        deactivate_chat(event.chat.id)


@router.message(Command("viloyat"))
async def viloyat_command(message: types.Message):
    """
    Гуруҳда исталган вақтда — вилоят(лар) боғлашни қайта очиш учун.
    Фақат ШУ ГУРУҲ учун тасдиқлаш ваколатига эга одам чақира олади.
    """
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("ℹ️ Бу буйруқ фақат гуруҳларда ишлайди.")
        return

    if not is_group_admin(message.chat.id, message.from_user.id):
        await message.answer("⚠️ Фақат шу гуруҳ учун тасдиқлаш ваколатига эга одам вилоят(лар)ни созлай олади.")
        return

    selected = set(get_regions_for_chat(message.chat.id))
    kb = _build_region_inline_kb(selected_regions=selected)
    await message.answer(
        "🏘 Бу гуруҳни қайси вилоят(лар)га боғлаймиз?\n\n"
        "(Бир нечта вилоят танлашингиз мумкин, ✅ — аллақачон танланган)",
        reply_markup=kb
    )


# ═══════════════════════════════════════
# БОШ АДМИН — гуруҳ тасдиқловчиларини бошқариш
# ═══════════════════════════════════════

@router.message(Command("addgroupadmin"))
async def add_group_admin_command(message: types.Message):
    """
    Бош админ (ADMINS) гуруҳда, керакли одамнинг хабарига REPLY қилиб
    шу буйруқни ёзса — ўша одам шу гуруҳ учун тасдиқловчи бўлади.
    """
    from config import ADMINS
    if message.from_user.id not in ADMINS:
        return
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("ℹ️ Бу буйруқ фақат гуруҳларда ишлайди.")
        return
    if not message.reply_to_message:
        await message.answer(
            "⚠️ Одамни белгилаш учун, унинг хабарига REPLY қилиб "
            "«/addgroupadmin» деб ёзинг."
        )
        return

    target = message.reply_to_message.from_user
    add_group_admin(message.chat.id, target.id, granted_by=message.from_user.id)
    await message.answer(
        f"✅ {target.full_name} энди шу гуруҳ учун эълон тасдиқлаш ваколатига эга."
    )


@router.message(Command("removegroupadmin"))
async def remove_group_admin_command(message: types.Message):
    """Бош админ — ваколатни олиб қўяди (REPLY орқали)."""
    from config import ADMINS
    if message.from_user.id not in ADMINS:
        return
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("ℹ️ Бу буйруқ фақат гуруҳларда ишлайди.")
        return
    if not message.reply_to_message:
        await message.answer(
            "⚠️ Одамни белгилаш учун, унинг хабарига REPLY қилиб "
            "«/removegroupadmin» деб ёзинг."
        )
        return

    target = message.reply_to_message.from_user
    remove_group_admin(message.chat.id, target.id)
    await message.answer(
        f"✅ {target.full_name} энди шу гуруҳ учун тасдиқлаш ваколатига эга ЭМАС."
    )


@router.callback_query(F.data.startswith("reggroup_"))
async def region_group_callback(callback: types.CallbackQuery):
    # ═══ ТЕЗ ЖАВОБ — Telegram callback muddati tugashini oldini olish ═══
    await callback.answer()

    chat_id = callback.message.chat.id

    if not is_group_admin(chat_id, callback.from_user.id):
        await callback.message.answer("⚠️ Фақат шу гуруҳ учун тасдиқлаш ваколатига эга одам танлаши мумкин.")
        return

    region = callback.data.replace("reggroup_", "")

    if region == "done":
        try:
            await callback.message.edit_text("✅ Созлаш якунланди. Раҳмат!")
        except Exception:
            pass
        return

    chat_title = callback.message.chat.title
    chat_username = callback.message.chat.username

    already_selected = region in get_regions_for_chat(chat_id)
    if already_selected:
        remove_region_group(chat_id, region)
    else:
        add_region_group(chat_id, chat_title, chat_username, region)

    # ═══ Ҳозиргача танланган БАРЧА вилоятларни олиб, ✅ билан ЎРНИДА янгилаймиз ═══
    selected = set(get_regions_for_chat(chat_id))
    new_text = (
        f"✅ Танланганлар: {', '.join(sorted(selected)) if selected else '(ҳали йўқ)'}\n\n"
        f"Яна вилоят қўшмоқчи бўлсангиз танланг, ёки якунлаш учун "
        f"«✅ Тугатиш» тугмасини босинг:"
    )
    try:
        await callback.message.edit_text(
            new_text,
            parse_mode="HTML",
            reply_markup=_build_region_inline_kb(selected_regions=selected)
        )
    except Exception as e:
        # "message is not modified" каби хатолар — зарарсиз, e'tibor bermaymiz
        logging.debug(f"Хабарни янгилашда (зарарсиз) хато: {e}")


# ═══════════════════════════════════════
# ГУРУҲДАГИ ✅/❌ — HAR BIR GURUH MUSTAQIL
# ═══════════════════════════════════════

@router.callback_query(F.data.startswith("gapprove_"))
async def group_approve_callback(callback: types.CallbackQuery):
    # ═══ ТЕЗ ЖАВОБ — birinchi navbatda ═══
    await callback.answer()

    post_id = int(callback.data.replace("gapprove_", ""))
    post = get_ad_group_post(post_id)
    if not post:
        await callback.message.answer("⚠️ Топилмади (эҳтимол аллақачон кўриб чиқилган).")
        return

    chat_id = callback.message.chat.id
    if not is_group_admin(chat_id, callback.from_user.id):
        await callback.message.answer("⚠️ Фақат шу гуруҳ учун тасдиқлаш ваколатига эга одам тасдиқлаши мумкин.")
        return

    review_ad_group_post(post_id, admin_id=callback.from_user.id, approve=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("greject_"))
async def group_reject_callback(callback: types.CallbackQuery):
    # ═══ ТЕЗ ЖАВОБ — birinchi navbatda ═══
    await callback.answer()

    post_id = int(callback.data.replace("greject_", ""))
    post = get_ad_group_post(post_id)
    if not post:
        await callback.message.answer("⚠️ Топилмади (эҳтимол аллақачон кўриб чиқилган).")
        return

    chat_id = callback.message.chat.id
    if not is_group_admin(chat_id, callback.from_user.id):
        await callback.message.answer("⚠️ Фақат шу гуруҳ учун тасдиқлаш ваколатига эга одам рад эта олади.")
        return

    review_ad_group_post(post_id, admin_id=callback.from_user.id, approve=False)
    try:
        await callback.message.delete()
    except Exception:
        pass
