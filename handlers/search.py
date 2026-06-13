import sqlite3
import html as html_module

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from database import search_all, fmt_number, parse_price_text, MAX_PRICE
from states import SearchStates
from keyboards import main_menu, search_animal_keyboard, regions_with_all_keyboard

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

    search_type = None if message.text == "Барчаси" else message.text
    await state.update_data(search_animal=search_type)
    await state.set_state(SearchStates.region)
    await message.answer(
        "📍 Қайси вилоятни қидирмоқчисиз?",
        reply_markup=regions_with_all_keyboard()
    )


@router.message(SearchStates.region)
async def search_region(message: types.Message, state: FSMContext):
    if message.text in ["🔙 Орқага", "❌ Бекор қилиш"]:
        return

    search_region_val = None if message.text == "Барчаси" else message.text
    data = await state.get_data()
    search_animal = data.get("search_animal")

    results = search_all(
        animal_type=search_animal,
        region=search_region_val
    )

    animal_text = search_animal if search_animal else "Барчаси"
    region_text = search_region_val if search_region_val else "Барча вилоятлар"

    # ═══ 1. УМИЙ МАЪЛУМОТ (БИР ХАБАР) ═══
    summary = f"🔍 *Қидириш натийжалари*\n"
    summary += f"🐾 {animal_text} | 📍 {region_text}\n"
    summary += f"{'─' * 30}\n\n"

    has_stats = False

    if results["stats"]:
        s = results["stats"]
        summary += f"📊 *УМИЙ МАЪЛУМОТ:*\n"
        summary += f"   📝 Маълумотлар: *{s['count']}* та\n"
        summary += f"   💰 Ўртача: *{fmt_number(s['avg'])}* сўм\n"
        summary += f"   ⬇️ Арзон: *{fmt_number(s['min'])}* сўм\n"
        summary += f"   ⬆️ Қиммат: *{fmt_number(s['max'])}* сўм\n\n"
        has_stats = True

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
        for region, prices in sorted_regions:
            avg = sum(prices) / len(prices)
            summary += f"  📍 *{region}*: {fmt_number(avg)} сўм"
            summary += f" ({len(prices)} та)\n"
        summary += "\n"
        has_stats = True

    # ═══ Эълонлар бор-йўқлигини текшириш ═══
    has_ads = len(results["ads"]) > 0

    if not has_stats and not has_ads:
        summary += (
            "❌ *Маълумот топилмади.*\n\n"
            "💡 *Тавсия:*\n"
            "• Бошқа ҳайвон турини синаб кўринг\n"
            '• "Барчаси", Вилоятини танланг\n'
            "• Ўзингиз нарх киритинг"
        )
    elif not has_stats and has_ads:
        summary += (
            "ℹ️ *Статистика ҳисоблана олмади*\n"
            "(нархлар нотўғри форматда киритилган)\n\n"
            f"📋 Лекин *{len(results['ads'])} та* эълон топилди ↓"
        )
    elif has_stats:
        s = results["stats"]
        summary += (
            f"💡 *Маслаҳат:*\n"
            f"Ўртача: {fmt_number(s['avg'] * 0.9)} — "
            f"{fmt_number(s['avg'] * 1.1)} сўм атрофида"
        )

    await message.answer(summary, parse_mode="Markdown", reply_markup=main_menu())

    # ═══ 2. ЭЪЛОНЛАР (алоҳида хабарлар + эгаси ҳаволаси) ═══
    if has_ads:
        await message.answer(
            f"📋 *Эълонлар ({len(results['ads'])} та):*",
            parse_mode="Markdown"
        )

        for i, ad in enumerate(results["ads"][:10], 1):
            ad_id, a_type, region, price, district, desc, qty, user_id = ad

            # ═══ HTML белгилардан тозалаш ═══
            safe_a_type = html_module.escape(str(a_type))
            safe_qty = html_module.escape(str(qty))
            safe_price = html_module.escape(str(price))
            safe_region = html_module.escape(str(region))
            safe_district = html_module.escape(str(district))
            safe_desc = html_module.escape(str(desc)) if desc else ""

            text = (
                f"<b>{i}.</b> 🐾 <b>{safe_a_type}</b> — {safe_qty}\n"
                f"   💰 {safe_price}\n"
                f"   📍 {safe_region}, {safe_district}\n"
            )

            if safe_desc and safe_desc != "Киритилмаган":
                text += f"   📝 {safe_desc}\n"

            # Эгаси — матн ичида ҳавола
            if user_id:
                text += f'   <a href="tg://user?id={user_id}">👤 Эгаси</a>'

            await message.answer(
                text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

    await state.clear()
