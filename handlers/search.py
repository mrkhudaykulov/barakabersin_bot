from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from database import search_all, fmt_number
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

    text = f"🔍 *Қидириш натийжалари*\n"
    text += f"🐾 {animal_text} | 📍 {region_text}\n"
    text += f"{'─' * 30}\n\n"

    has_data = False

    # ── 1. СТАТИСТИКА ──
    if results["stats"]:
        s = results["stats"]
        text += f"📊 *УМИЙ МАЪЛУМОТ:*\n"
        text += f"   📝 Маълумотлар: *{s['count']}* та\n"
        text += f"   💰 Ўртача: *{fmt_number(s['avg'])}* сўм\n"
        text += f"   ⬇️ Арзон: *{fmt_number(s['min'])}* сўм\n"
        text += f"   ⬆️ Қиммат: *{fmt_number(s['max'])}* сўм\n\n"
        has_data = True

    # ── 2. БОЗОР НАРХЛАРИ ──
    if results["market_prices"]:
        by_region = {}
        for mp in results["market_prices"]:
            r = mp[1]
            p = mp[2]
            if r not in by_region:
                by_region[r] = []
            by_region[r].append(p)

        text += f"📈 *БОЗОР НАРХЛАРИ:*\n"
        sorted_regions = sorted(
            by_region.items(),
            key=lambda x: sum(x[1]) / len(x[1])
        )
        for region, prices in sorted_regions:
            avg = sum(prices) / len(prices)
            text += f"  📍 *{region}*: {fmt_number(avg)} сўм"
            text += f" ({len(prices)} та)\n"
        text += "\n"
        has_data = True

    # ── 3. ЭЪЛОНЛАР ──
    if results["ads"]:
        text += f"📋 *ЭЪЛОНЛАР ({len(results['ads'])} та):*\n\n"
        for i, ad in enumerate(results["ads"][:5], 1):
            a_type, region, price, district, desc, qty = ad
            text += f"*{i}.* {a_type} — {qty}\n"
            text += f"   💰 {price}\n"
            text += f"   📍 {region}, {district}\n"
            if desc and desc != "Киритилмаган":
                text += f"   📝 {desc}\n"
            text += "\n"
        has_data = True

    # ── 4. ТОПИЛМАСА ──
    if not has_data:
        text += (
            "❌ *Маълумот топилмади.*\n\n"
            "💡 *Тавсия:*\n"
            "• Бошқа ҳайвон турини синаб кўринг\n"
            '• "Барчаси" вилоятини танланг\n'
            "• Ўзингиз нарх киритинг"
        )
    elif results["stats"]:
        s = results["stats"]
        text += (
            f"💡 *Маслаҳат:*\n"
            f"Ўртача: {fmt_number(s['avg'] * 0.9)} — "
            f"{fmt_number(s['avg'] * 1.1)} сўм атрофида"
        )

    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu())
    await state.clear()
