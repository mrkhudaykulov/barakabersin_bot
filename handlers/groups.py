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

import asyncio
import html
import logging

from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from keyboards import DISTRICTS
from database import (
    add_region_group, remove_region_group, deactivate_chat, get_regions_for_chat,
    get_all_active_group_chat_ids, get_blocks_by_admin,
    add_group_admin, remove_group_admin, is_group_admin, get_chats_managed_by,
    get_group_admin_ids,
)

router = Router()

REGIONS = list(DISTRICTS.keys())


async def get_user_managed_groups(user_id: int):
    """
    Фойдаланувчи ТАСДИҚЛАШ ВАКОЛАТИГА эга бўлган гуруҳлар — БИЗНИНГ
    group_admins жадвалидан (Telegram API'га мурожаат қилинмайди, тезроқ).
    Қайтаради: [(chat_id, chat_title, regions_list), ...]
    """
    chat_ids = await get_chats_managed_by(user_id)
    if not chat_ids:
        return []
    all_groups = await get_all_active_group_chat_ids()
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
    blocks = await get_blocks_by_admin(message.from_user.id)
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

    all_groups = await get_all_active_group_chat_ids()
    if not all_groups:
        await message.answer("ℹ️ Ҳозирча ҳеч қандай гуруҳ боғланмаган.")
        return

    text = f"🏘 <b>Уланган гуруҳлар ({len(all_groups)} та):</b>\n\n"
    buttons = []
    for chat_id, info in all_groups.items():
        uname = f"@{info['chat_username']}" if info["chat_username"] else "приват"
        text += (
            f"• <b>{info['chat_title']}</b> ({uname})\n"
            f"   Вилоят(лар): {', '.join(info['regions'])}\n\n"
        )
        buttons.append([InlineKeyboardButton(
            text=f"❌ Ўчириш: {info['chat_title']}",
            callback_data=f"rmgroup_{chat_id}"
        )])
    text += (
        "\n<i>Агар бир гуруҳ рўйхатда такрорланиб турса (масалан, "
        "оддий гуруҳ супергуруҳга айлантирилгандан кейин) — "
        "эскисини қуйидаги тугма орқали ўчириб ташланг.</i>"
    )
    await message.answer(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("rmgroup_"))
async def remove_connected_group_callback(callback: types.CallbackQuery):
    """Фақат бош админлар учун — рўйхатдаги бир гуруҳ ёзувини фаолсизлантиради."""
    from config import ADMINS
    if callback.from_user.id not in ADMINS:
        await callback.answer("⛔ Сизга бу амал учун рухсат йўқ.", show_alert=True)
        return

    chat_id = int(callback.data.replace("rmgroup_", ""))
    await deactivate_chat(chat_id)
    await callback.answer("✅ Ўчирилди.")
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n🗑 <i>Юқоридаги гуруҳлардан бири ўчирилди — рўйхатни "
            "янгилаш учун \"🏘 Уланган гуруҳлар\"ни қайта босинг.</i>",
            parse_mode="HTML"
        )
    except Exception:
        pass


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
        # Бот янги қўшилди — ҚЎШГАН ОДАМ шу гуруҳнинг ВИЛОЯТ созламаларини
        # бошқариш ваколатига эга бўлади (эълон тасдиқлаш ваколати ЭМАС —
        # у энди бош админ орқали, алоҳида берилади).
        await add_group_admin(event.chat.id, event.from_user.id, granted_by=None)

        kb = _build_region_inline_kb()
        try:
            await bot.send_message(
                chat_id=event.chat.id,
                text=(
                    "🐄🐑🐐 <b>Чорва Бозор боти шу гуруҳга қўшилди!</b> 🐫🐴🐓\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "👋 Салом ҳаммага! Мен чорва мол-ҳол (сигир, қўй, эчки, "
                    "от ва ҳ.к.) олди-сотдисида ёрдам берадиган ботман. "
                    "Мана мен нима қила оламан:\n\n"

                    "📢 <b>Янги эълонларни ўзим жойлайман</b>\n"
                    "Сиз танлаган вилоят(лар)да кимдир мол сотмоқчи бўлса, "
                    "унинг эълони (расм/видео, нархи, манзили, телефони "
                    "билан) тўғри шу гуруҳга — қўлда жойлаштиришсиз, "
                    "автомат тушади. 🖇\n\n"

                    "✅ <b>Фақат тасдиқланганлари</b>\n"
                    "Ҳар бир эълон гуруҳга тушишидан олдин админ томонидан "
                    "текширилади — шунинг учун гуруҳда фақат ишончли, "
                    "тоза эълонларни кўрасиз. 🛡\n\n"

                    "🤝 <b>Харидор ва сотувчини боғлайман</b>\n"
                    "Эълондаги телефон рақами орқали харидорлар тўғри "
                    "сотувчига мурожаат қила олади — оралиқда восита йўқ.\n\n"

                    "💬 <b>Бунинг устига, мен билан шахсий чатда:</b>\n"
                    "🔍 Эълонларни вилоят/туман/нарх бўйича қидиришингиз;\n"
                    "🩺 Веб ветеринария ходимларининг алоқаларини топишингиз;\n"
                    "🔔 Ўзингизга қизиқ мезон бўйича хабардор бўлиб, мос "
                    "эълон чиқса дарҳол хабар олишингиз мумкин.\n\n"

                    "👇 Аввало, бу гуруҳни қайси вилоят(лар)га боғлаймиз? "
                    "Пастдаги тугмалардан танланг (бир нечтасини танлаш "
                    "мумкин):"
                ),
                parse_mode="HTML"
            )
            await bot.send_message(
                chat_id=event.chat.id,
                text=(
                    f"✅ Сиз ({event.from_user.full_name}) шу гуруҳ учун "
                    f"вилоят(лар)ни созлаш ваколатига эга бўлдингиз.\n\n"
                    "Танланган вилоят(лар)дан эълон тасдиқлансa, шу гуруҳга "
                    "ҳам автомат жойланади:"
                ),
                reply_markup=kb
            )
        except Exception as e:
            logging.warning(f"Гуруҳга (chat_id={event.chat.id}) хабар юборилмади: {e}")
            # ═══ Кўпинча сабаби — ботга ёзиш ҳуқуқи йўқ (chat_admin_required
            # ёки "фақат админлар ёзади" чеклови). Буни қўшган одамга
            # ШАХСИЙ чатда тушунтирамиз — акс ҳолда у бунинг сабабини
            # ҳеч қачон билмайди, чунки гуруҳда бот умуман ёза олмайди ═══
            try:
                await bot.send_message(
                    chat_id=event.from_user.id,
                    text=(
                        f"⚠️ Мен «{html.escape(event.chat.title or '')}» гуруҳига "
                        f"қўшилдим, лекин у ерга ХАБАР ЁЗА ОЛМАДИМ.\n\n"
                        f"🔧 <b>Сабаби (техник):</b> <code>{html.escape(str(e))}</code>\n\n"
                        f"Кўпинча бунинг сабаби шу иккитадан бири:\n"
                        f"1️⃣ Менга (ботга) ҳали администратор ҳуқуқи берилмаган;\n"
                        f"2️⃣ Гуруҳда «Фақат админлар хабар юбора олади» деган "
                        f"чеклов ёқилган.\n\n"
                        f"✅ <b>Ечими:</b> гуруҳ созламаларида мени "
                        f"администратор қилиб қўйинг (ёки ёзиш чекловини "
                        f"олиб ташланг), сўнг гуруҳда қайта «/viloyat» "
                        f"буйруғини юборинг — шунда вилоят(лар) боғлашни "
                        f"давом эттира оласиз."
                    ),
                    parse_mode="HTML"
                )
            except Exception as inner_e:
                logging.warning(
                    f"Гуруҳни қўшган одамга ({event.from_user.id}) ҳам "
                    f"огоҳлантириш юборилмади: {inner_e}"
                )

        # ═══ БОШ АДМИНЛАРГА БИЛДИРИШНОМА ═══
        await _notify_bosh_admins_about_new_group(event.chat, event.from_user)

    elif was_in and not is_in:
        # Бот чиқарилди/чиқиб кетди
        await deactivate_chat(event.chat.id)


@router.message(F.migrate_to_chat_id)
async def on_group_migrated_to_supergroup(message: types.Message):
    """
    Оддий гуруҳ супергуруҳга айлантирилганда Telegram янги chat_id беради —
    эскиси ортда "ўлик" қолиб, дублик ёзувга олиб келади. Шу ерда эски
    chat_id'даги вилоят(лар) ва гуруҳ-админлар янги chat_id'га кўчирилади,
    эскиси эса фаолсизлантирилади.
    """
    old_chat_id = message.chat.id
    new_chat_id = message.migrate_to_chat_id

    regions = await get_regions_for_chat(old_chat_id)
    if regions:
        for region in regions:
            await add_region_group(new_chat_id, message.chat.title, message.chat.username, region)

    for admin_id in await get_group_admin_ids(old_chat_id):
        await add_group_admin(new_chat_id, admin_id, granted_by=None)

    await deactivate_chat(old_chat_id)
    logging.info(f"Гуруҳ супергуруҳга айлантирилди: {old_chat_id} -> {new_chat_id}, вилоятлар кўчирилди: {regions}")


async def _notify_bosh_admins_about_new_group(chat, adder):
    """
    Бот янги гуруҳга қўшилганда — бош ADMINS'га гуруҳ ва уни қўшган
    одам ҳақида хабар юборади, "Review admin қилиб қўшиш" тугмаси билан.
    """
    from config import ADMINS

    group_link = f"https://t.me/{chat.username}" if chat.username else "(приват, ҳаволаси йўқ)"
    adder_username = f"@{adder.username}" if adder.username else "(username йўқ)"
    adder_profile = f"tg://user?id={adder.id}"

    text = (
        f"🆕 <b>Бот янги гуруҳга қўшилди!</b>\n\n"
        f"🏘 <b>Гуруҳ:</b> {html.escape(chat.title or '—')}\n"
        f"🔗 <b>Ҳавола:</b> {group_link}\n\n"
        f"👤 <b>Қўшган одам:</b> {html.escape(adder.full_name)}\n"
        f"💬 <b>Username:</b> {adder_username}\n"
        f"🆔 <b>ID:</b> <code>{adder.id}</code>\n"
        f"🔗 <a href='{adder_profile}'>Профилга ўтиш</a>\n\n"
        f"Шу одамни яxлит эълон тасдиқлаш ҳавзасига (review admin) қўшасизми?"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Review admin қилиб қўшиш",
            callback_data=f"addreviewadmin_{adder.id}"
        )
    ]])

    for bosh_admin_id in ADMINS:
        try:
            await bot.send_message(
                chat_id=bosh_admin_id, text=text,
                parse_mode="HTML", reply_markup=kb
            )
        except Exception as e:
            logging.warning(f"Бош админга ({bosh_admin_id}) билдиришнома юборилмади: {e}")


@router.callback_query(F.data.startswith("addreviewadmin_"))
async def add_review_admin_callback(callback: types.CallbackQuery):
    """Бош админ тугмани босиб, одамни яxлит review_admins ҳавзасига қўшади."""
    from config import ADMINS
    from database import add_review_admin

    if callback.from_user.id not in ADMINS:
        await callback.answer("⛔ Сизга бу амал учун рухсат йўқ.", show_alert=True)
        return

    target_user_id = int(callback.data.replace("addreviewadmin_", ""))

    full_name = None
    username = None
    try:
        chat_info = await bot.get_chat(target_user_id)
        full_name = chat_info.full_name
        username = chat_info.username
    except Exception:
        pass

    await add_review_admin(
        target_user_id, full_name=full_name, username=username,
        added_by=callback.from_user.id
    )

    await callback.answer("✅ Қўшилди!")
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>REVIEW ADMIN сифатида қўшилди.</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.message(Command("reviewadmins"))
async def list_review_admins_command(message: types.Message, command: CommandObject):
    """
    Бош админ учун — яxлит review_admins ҳавзасидаги барча одамлар
    рўйхати, ҳар бирининг олдида «❌ Олиб ташлаш» тугмаси билан.
    Исталган жойда (приват чат ёки гуруҳда) ишлайди.

    Янги одам ҚЎШИШ учун:
      • Гуруҳда — керакли одамнинг хабарига REPLY қилиб «/reviewadmins add»;
      • Ёки исталган жойда — «/reviewadmins add 123456789» (USER_ID билан).
    """
    from config import ADMINS
    from database import get_all_review_admin_ids, add_review_admin

    if message.from_user.id not in ADMINS:
        return

    args = (command.args or "").strip().split()

    if args and args[0].lower() == "add":
        target_id = None
        target_name = None
        target_username = None

        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            target_id = target_user.id
            target_name = target_user.full_name
            target_username = target_user.username
        elif len(args) > 1 and args[1].isdigit():
            target_id = int(args[1])
            try:
                chat_info = await bot.get_chat(target_id)
                target_name = chat_info.full_name
                target_username = chat_info.username
            except Exception:
                target_name = None
                target_username = None
        else:
            await message.answer(
                "⚠️ Одамни белгилаш учун:\n"
                "• унинг хабарига REPLY қилиб «/reviewadmins add» деб ёзинг,\n"
                "• ёки «/reviewadmins add USER_ID» шаклида юборинг."
            )
            return

        await add_review_admin(
            target_id, full_name=target_name, username=target_username,
            added_by=message.from_user.id
        )
        uname = f"@{target_username}" if target_username else f"ID: {target_id}"
        await message.answer(
            f"✅ {target_name or uname} энди яxлит review admins ҳавзасида — "
            f"эълонларни тасдиқлаш/рад этиш ваколатига эга."
        )
        return

    ids = await get_all_review_admin_ids()
    if not ids:
        await message.answer("ℹ️ Review admins ҳавзаси ҳозирча бўш.")
        return

    await message.answer(f"👥 <b>Review admins ({len(ids)} та):</b>", parse_mode="HTML")

    for uid in ids:
        try:
            chat_info = await bot.get_chat(uid)
            label = chat_info.full_name
            uname = f"@{chat_info.username}" if chat_info.username else ""
        except Exception:
            label = f"ID: {uid}"
            uname = ""

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Олиб ташлаш", callback_data=f"removereviewadmin_{uid}")
        ]])
        await message.answer(
            f"👤 {html.escape(label)} {uname}\n🆔 <code>{uid}</code>",
            parse_mode="HTML",
            reply_markup=kb
        )


@router.callback_query(F.data.startswith("removereviewadmin_"))
async def remove_review_admin_callback(callback: types.CallbackQuery):
    """Бош админ — «❌ Олиб ташлаш» тугмаси орқали review_admins'дан чиқаради."""
    from config import ADMINS
    from database import remove_review_admin

    if callback.from_user.id not in ADMINS:
        await callback.answer("⛔ Сизга бу амал учун рухсат йўқ.", show_alert=True)
        return

    target_user_id = int(callback.data.replace("removereviewadmin_", ""))
    await remove_review_admin(target_user_id)

    await callback.answer("✅ Олиб ташланди!")
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ <b>Ҳавзадан олиб ташланди.</b>",
            parse_mode="HTML",
            reply_markup=None
        )
    except Exception:
        pass


@router.message(Command("viloyat"))
async def viloyat_command(message: types.Message):
    """
    Гуруҳда исталган вақтда — вилоят(лар) боғлашни қайта очиш учун.
    Фақат ШУ ГУРУҲ учун тасдиқлаш ваколатига эга одам чақира олади.
    """
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("ℹ️ Бу буйруқ фақат гуруҳларда ишлайди.")
        return

    if not await is_group_admin(message.chat.id, message.from_user.id):
        await message.answer("⚠️ Фақат шу гуруҳ учун тасдиқлаш ваколатига эга одам вилоят(лар)ни созлай олади.")
        return

    selected = set(await get_regions_for_chat(message.chat.id))
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
    await add_group_admin(message.chat.id, target.id, granted_by=message.from_user.id)
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
    await remove_group_admin(message.chat.id, target.id)
    await message.answer(
        f"✅ {target.full_name} энди шу гуруҳ учун тасдиқлаш ваколатига эга ЭМАС."
    )


@router.callback_query(F.data.startswith("reggroup_"))
async def region_group_callback(callback: types.CallbackQuery):
    # ═══ ТЕЗ ЖАВОБ — Telegram callback muddati tugashини oldini olish ═══
    await callback.answer()

    chat_id = callback.message.chat.id
    region = callback.data.replace("reggroup_", "")

    # ═══ Рухсат текшируви ва жорий вилоятлар рўйхатини ПАРАЛЛЕЛ оламиз —
    # кетма-кет 4 та алоҳида DB сўрови ўрнига, тугма босилгандан тортиб
    # хабар янгилангунча кечикиш сезиларли қисқаради ═══
    is_admin, current_regions = await asyncio.gather(
        is_group_admin(chat_id, callback.from_user.id),
        get_regions_for_chat(chat_id),
    )

    if not is_admin:
        await callback.message.answer("⚠️ Фақат шу гуруҳ учун тасдиқлаш ваколатига эга одам танлаши мумкин.")
        return

    if region == "done":
        try:
            await callback.message.edit_text("✅ Созлаш якунланди. Раҳмат!")
        except Exception:
            pass
        return

    chat_title = callback.message.chat.title
    chat_username = callback.message.chat.username

    selected = set(current_regions)
    if region in selected:
        await remove_region_group(chat_id, region)
        selected.discard(region)
    else:
        await add_region_group(chat_id, chat_title, chat_username, region)
        selected.add(region)

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
# ЭСЛАТМА: Гуруҳдаги мустақил ✅/❌ тугмалари ва per-group moderatsiya
# ОЛИБ ТАШЛАНДИ — энди эълон тасдиқлаш МАРКАЗЛАШГАН (review_admins орқали,
# ads.py'да). Тасдиқлангандан кейин эълон АВТОМАТИК гуруҳга жойланади
# (ads.py'даги post_ad_to_matching_groups орқали, тугмасиз, тайёр ҳолда).
# ═══════════════════════════════════════
