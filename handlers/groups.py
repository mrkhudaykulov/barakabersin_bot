"""
groups.py

Ботни гуруҳга қўшилганда — қайси вилоят(лар)га боғлашни сўрайди
(inline тугмалар орқали, faqat guruh admin/egasi tanlashi mumkin).

Эълон яратилганда (ads.py'даги _finalize_ad'дан), шу вилоятга боғланган
барча актив гуруҳларга ✅/❌ тугмали хабар юборилади. Ҳар бир гуруҳ ўз
админи томонидан МУСТАҚИЛ тасдиқланади/рад этилади — каналдаги
REVIEW_ADMINS тасдиғига ҳеч қандай алоқаси йўқ.
"""

import logging

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from keyboards import DISTRICTS
from database import (
    add_region_group, deactivate_chat,
    get_ad_group_post, review_ad_group_post,
    get_all_active_group_chat_ids, get_blocks_by_admin
)

router = Router()

REGIONS = list(DISTRICTS.keys())


async def get_user_managed_groups(user_id: int):
    """
    Фойдаланувчи (истаган одам) ҳақиқатан қайси боғланган гуруҳларда
    админ/эга эканини Telegram'нинг ўзидан жонли текширади.
    Қайтаради: [(chat_id, chat_title, regions_list), ...]
    """
    all_groups = get_all_active_group_chat_ids()
    result = []
    for chat_id, info in all_groups.items():
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status in ("administrator", "creator"):
                result.append((chat_id, info["chat_title"], info["regions"]))
        except Exception:
            continue
    return result


@router.message(F.text == "🏘 Менинг гуруҳларим")
async def my_managed_groups(message: types.Message):
    groups = await get_user_managed_groups(message.from_user.id)
    if not groups:
        await message.answer(
            "ℹ️ Сиз ҳозирча ҳеч қандай боғланган гуруҳда админ эмассиз."
        )
        return

    text = "🏘 <b>Сиз админ бўлган гуруҳлар:</b>\n\n"
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


def _build_region_inline_kb():
    buttons = []
    row = []
    for r in REGIONS:
        row.append(InlineKeyboardButton(text=r, callback_data=f"reggroup_{r}"))
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
    my_chat_member Telegram'да ФАҚАТ ботнинг ўз ҳолати ўзгарганда келади —
    бошқа фойдаланувчилар учун чақирилмайди.
    """
    if event.chat.type not in ("group", "supergroup"):
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    was_in = old_status in ("member", "administrator", "creator")
    is_in = new_status in ("member", "administrator", "creator")

    if not was_in and is_in:
        # Бот янги қўшилди
        kb = _build_region_inline_kb()
        try:
            await bot.send_message(
                chat_id=event.chat.id,
                text=(
                    "👋 Салом! Ботни ушбу гуруҳга қўшганингиз учун раҳмат.\n\n"
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
    Фақат гуруҳларда ишлайди, ва фақат ўша гуруҳнинг ҳақиқий
    админи/эгаси чақира олади.
    """
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("ℹ️ Бу буйруқ фақат гуруҳларда ишлайди.")
        return

    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("administrator", "creator"):
        await message.answer("⚠️ Фақат гуруҳ админи вилоят(лар)ни созлай олади.")
        return

    kb = _build_region_inline_kb()
    await message.answer(
        "🏘 Бу гуруҳни қайси вилоят(лар)га боғлаймиз?\n\n"
        "(Бир нечта вилоят танлашингиз мумкин)",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("reggroup_"))
async def region_group_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id

    # Фақат шу гуруҳнинг ҳақиқий админи/эгаси танлаши мумкин
    member = await bot.get_chat_member(chat_id, callback.from_user.id)
    if member.status not in ("administrator", "creator"):
        await callback.answer("⚠️ Фақат гуруҳ админи танлаши мумкин.", show_alert=True)
        return

    region = callback.data.replace("reggroup_", "")

    if region == "done":
        await callback.message.edit_text("✅ Созлаш якунланди. Раҳмат!")
        await callback.answer()
        return

    chat_title = callback.message.chat.title
    chat_username = callback.message.chat.username
    add_region_group(chat_id, chat_title, chat_username, region)

    await callback.answer(f"✅ {region} қўшилди!")
    await callback.message.answer(
        f"✅ Бу гуруҳ энди <b>{region}</b> вилояти учун ҳам эълонларни олади.\n\n"
        f"Яна вилоят қўшмоқчи бўлсангиз танланг, ёки якунлаш учун "
        f"«✅ Тугатиш» тугмасини босинг:",
        parse_mode="HTML",
        reply_markup=_build_region_inline_kb()
    )


# ═══════════════════════════════════════
# ГУРУҲДАГИ ✅/❌ — HAR BIR GURUH MUSTAQIL
# ═══════════════════════════════════════

@router.callback_query(F.data.startswith("gapprove_"))
async def group_approve_callback(callback: types.CallbackQuery):
    post_id = int(callback.data.replace("gapprove_", ""))
    post = get_ad_group_post(post_id)
    if not post:
        await callback.answer("⚠️ Топилмади (эҳтимол аллақачон кўриб чиқилган).", show_alert=True)
        return

    chat_id = callback.message.chat.id
    member = await bot.get_chat_member(chat_id, callback.from_user.id)
    if member.status not in ("administrator", "creator"):
        await callback.answer("⚠️ Фақат гуруҳ админи тасдиқлаши мумкин.", show_alert=True)
        return

    review_ad_group_post(post_id, admin_id=callback.from_user.id, approve=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("✅ Тасдиқланди!")


@router.callback_query(F.data.startswith("greject_"))
async def group_reject_callback(callback: types.CallbackQuery):
    post_id = int(callback.data.replace("greject_", ""))
    post = get_ad_group_post(post_id)
    if not post:
        await callback.answer("⚠️ Топилмади (эҳтимол аллақачон кўриб чиқилган).", show_alert=True)
        return

    chat_id = callback.message.chat.id
    member = await bot.get_chat_member(chat_id, callback.from_user.id)
    if member.status not in ("administrator", "creator"):
        await callback.answer("⚠️ Фақат гуруҳ админи рад эта олади.", show_alert=True)
        return

    review_ad_group_post(post_id, admin_id=callback.from_user.id, approve=False)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("❌ Рад этилди ва ўчирилди.")
