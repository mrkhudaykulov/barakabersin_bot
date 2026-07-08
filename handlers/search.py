import html as html_module

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
import logging

from database import (
    get_connection, get_placeholder, parse_price_text, fmt_number,
    get_full_statistics, MAX_PRICE, MIN_PRICE, fix_keyboard_text,
    match_price_index, search_all, is_premium_user,  # ← қўшилди
    get_ad_group_links  # ← гуруҳ ҳаволалари учун
)
from states import SearchStates
from keyboards import main_menu, search_animal_keyboard, regions_with_all_keyboard, notification_districts_keyboard

# ЁРДАМЧИ ФУНКЦИЯ
def is_all_districts(text):
    """Барчаси"""
    if not text:
        return False
    return "Барчаси" in text
    
router = Router()


@router.message(F.text == "🔍 Эълон қидириш")
async def search_start(message: types.Message, state: FSMContext):
    await state.set_state(SearchStates.animal_type)
    await message.answer(
        "🔍 *Эълон қидириш*\n\n"
        "Қайси ҳайвон турини қидирмоқчисиз?",
        parse_mode="Markdown",
        reply_markup=search_animal_keyboard()
    )


@router.message(SearchStates.animal_type)
async def search_animal(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return

    fixed = fix_keyboard_text(message.text)
    search_type = None if fixed == "Барчаси" else fixed
    await state.update_data(search_animal=search_type)
    logging.info(f"Search animal_type: '{search_type}'")
    await state.set_state(SearchStates.region)
    await message.answer(
        "📍 Қайси вилоятни қидирмоқчисиз?",
        reply_markup=regions_with_all_keyboard()
    )

@router.message(SearchStates.region)
async def search_region(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return

    fixed = fix_keyboard_text(message.text)
    await state.update_data(region=fixed)
    await state.set_state(SearchStates.district)
    await message.answer(
        "🏘 Қайси туманда қидирилади?\n\n"
        "_Ёки *📍 Барчаси* тугмасини танланг._",
        parse_mode="Markdown",
        reply_markup=notification_districts_keyboard(fixed)
    )


@router.message(SearchStates.district)
async def search_district(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        await state.clear()
        await message.answer("❌ Бекор қилинди.", reply_markup=main_menu())
        return

    data = await state.get_data()
    search_animal = data.get("search_animal")
    region = data.get("region")

    # Туман аниқлаш
    if is_all_districts(message.text):
        search_district_val = None
        district_text = "Барча туманлар"
    else:
        search_district_val = fix_keyboard_text(message.text)
        district_text = search_district_val

    # ═══ ЛИМИТ ═══
    user_id = message.from_user.id
    if is_premium_user(user_id):
        search_limit = 50
        user_label = "Премиум"
    else:
        search_limit = 5
        user_label = "Оддий"

    search_region_val = None if region == "Барчаси" else region

    logging.info(
        f"Searching: animal='{search_animal}', region='{search_region_val}', "
        f"district='{search_district_val}', limit={search_limit}"
    )

    results = search_all(
        animal_type=search_animal,
        region=search_region_val,
        district=search_district_val,
        limit=search_limit
    )

    logging.info(
        f"Results: ads={len(results['ads'])}, "
        f"mp={len(results['market_prices'])}, "
        f"stats={bool(results['stats'])}"
    )

    animal_text = search_animal if search_animal else "Барчаси"
    region_text = search_region_val if search_region_val else "Барча вилоятлар"

    # ═══ 1. УМИЙ МАЪЛУМОТ ═══
    summary = f"🔍 *Қидириш натижалари*\n"
    summary += f"🐾 {animal_text} | 📍 {region_text}, {district_text}\n"
    summary += f"👤 {user_label} лимит: {search_limit} та\n"
    summary += f"{'─' * 30}\n\n"

    has_stats = bool(results["stats"])

    if has_stats:
        s = results["stats"]
        summary += f"📊 *УМИЙ МАЪЛУМОТ:*\n"
        summary += f"   📝 Маълумотлар: *{s['count']}* та\n"
        summary += f"   💰 Ўртача: *{fmt_number(s['avg'])}* сўм\n"
        summary += f"   ⬇️ Арзон: *{fmt_number(s['min'])}* сўм\n"
        summary += f"   ⬆️ Қиммат: *{fmt_number(s['max'])}* сўм\n\n"

    if results["market_prices"]:
        by_region = {}
        for mp in results["market_prices"]:
            r = mp[1]
            p = mp[2]
            if r not in by_region:
                by_region[r] = []
            by_region[r].append(p)

        summary += f"📈 *БОЗОР НАРХЛАРИ:*\n"
        sorted_regions = sorted(
            by_region.items(),
            key=lambda x: sum(x[1]) / len(x[1])
        )
        for rgn, prices in sorted_regions:
            avg = sum(prices) / len(prices)
            summary += f"  📍 *{rgn}*: {fmt_number(avg)} сўм"
            summary += f" ({len(prices)} та)\n"
        summary += "\n"
        has_stats = True

    has_ads = len(results["ads"]) > 0

    if not has_stats and not has_ads:
        summary += (
            "❌ *Маълумот топилмади.*\n\n"
            "💡 *Тавсия:*\n"
            "• Бошқа ҳайвон турини синаб кўринг\n"
            "• Бошқа туманни танланг\n"
            "• Ўзингиз нарх киритинг"
        )
    elif not has_stats and has_ads:
        summary += (
            "ℹ️ *Статистика ҳисоблана олмади*\n"
            "(нархлар нотўғри форматда)\n\n"
            f"📋 Лекин *{len(results['ads'])} та* эълон топилди ↓"
        )
    elif has_stats:
        s = results["stats"]
        summary += (
            f"💡 *Маслаҳат:*\n"
            f"Ўртача: {fmt_number(s['avg'] * 0.9)} — "
            f"{fmt_number(s['avg'] * 1.1)} сўм атрофида"
        )

    await message.answer(
        summary, parse_mode="Markdown", reply_markup=main_menu()
    )

    # ═══ 2. ЭЪЛОНЛАР ═══
    if has_ads:
        await message.answer(
            f"📋 *Эълонлар ({len(results['ads'])} та):*",
            parse_mode="Markdown"
        )

        for i, ad in enumerate(results["ads"][:search_limit], 1):
            try:
                ad_id = ad[0]
                a_type = str(ad[1]) if ad[1] else ""
                rgn = str(ad[2]) if ad[2] else ""
                price = str(ad[3]) if ad[3] else ""
                district = str(ad[4]) if ad[4] else ""
                desc = str(ad[5]) if ad[5] else ""
                qty = str(ad[6]) if ad[6] else ""
                user_id_ad = ad[7] if len(ad) > 7 else None
                msg_id_str = str(ad[8]) if len(ad) > 8 and ad[8] else ""

                safe_type = html_module.escape(a_type)
                safe_qty = html_module.escape(qty)
                safe_price = html_module.escape(price)
                safe_region = html_module.escape(rgn)
                safe_dist = html_module.escape(district)
                safe_desc = html_module.escape(desc)

                text = (
                    f"<b>{i}.</b> <b>{safe_type}</b> — {safe_qty}\n"
                    f"   💰 {safe_price}\n"
                    f"   📍 {safe_region}, {safe_dist}"
                )

                if safe_desc and safe_desc != "Киритилмаган":
                    text += f"\n   📝 {safe_desc}"

                if msg_id_str:
                    first_msg_id = msg_id_str.split(",")[0].strip()
                    channel_username = "internetmolbozor"
                    ad_link = f"https://t.me/{channel_username}/{first_msg_id}"
                    text += f'   <a href="{ad_link}">👁кўриш (канал)</a>'

                # ═══ Вилоят гуруҳларидаги ҳаволалар (агар бор бўлса) ═══
                group_links = get_ad_group_links(ad_id)
                for idx, glink in enumerate(group_links, 1):
                    text += f'\n   <a href="{glink}">👁кўриш (гуруҳ {idx})</a>'

                await message.answer(
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

            except Exception as e:
                logging.error(f"Эълон #{i} хато: {e}")
                try:
                    safe_text = (
                        f"{i}. {ad[1]} — {ad[6]}\n"
                        f"   💰 {ad[3]}\n"
                        f"   📍 {ad[2]}, {ad[4]}"
                    )
                    await message.answer(safe_text)
                except Exception:
                    pass

    else:
        await message.answer(
            "📭 *Эълонлар ҳозирда мавжуд эмас.*\n\n"
            "Кейинроқ қайта уриниб кўринг ёки бошқа параметрлар билан қидиринг.",
            parse_mode="Markdown"
        )

    # Оддий фойдаланувчига премиум таклифи
    if not is_premium_user(message.from_user.id) and len(results["ads"]) >= 5:
        await message.answer(
            "💎 *Кўпроқ натижа кўриш учун Премиум аъзо бўлинг!*\n\n"
            "Оддий: 5 та | Премиум: 50 та натижа",
            parse_mode="Markdown"
        )

    await state.clear()


@router.message(SearchStates.animal_type)
async def search_animal_fallback(message: types.Message, state: FSMContext):
    """Qidiruv — hayvon turida noto'g'ri matn"""
    await message.answer(
        "⚠️ Тугмалардан бирини танланг:",
        reply_markup=search_animal_keyboard()
    )


@router.message(SearchStates.region)
async def search_region_fallback(message: types.Message, state: FSMContext):
    """Qidiruv — viloyatda noto'g'ri matn"""
    await message.answer(
        "⚠️ Тугмалардан бирини танланг:",
        reply_markup=regions_with_all_keyboard()
    )

@router.message(SearchStates.district)
async def search_district_fallback(message: types.Message, state: FSMContext):
    """Qidiruv — tumanda noto'g'ri matn"""
    data = await state.get_data()
    region = data.get("region", "")
    await message.answer(
        "⚠️ Тугмалардан бирини танланг:",
        reply_markup=notification_districts_keyboard(region)
    )
