import html as html_module

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
import logging

from database import search_all, fmt_number, fix_keyboard_text, get_connection, get_placeholder
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
    search_region_val = None if fixed == "Барчаси" else fixed
    data = await state.get_data()
    search_animal = data.get("search_animal")

    logging.info(
        f"Searching: animal='{search_animal}', region='{search_region_val}'"
    )

    results = search_all(
        animal_type=search_animal,
        region=search_region_val
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
    summary += f"🐾 {animal_text} | 📍 {region_text}\n"
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
        for region, prices in sorted_regions:
            avg = sum(prices) / len(prices)
            summary += f"  📍 *{region}*: {fmt_number(avg)} сўм"
            summary += f" ({len(prices)} та)\n"
        summary += "\n"
        has_stats = True

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

        for i, ad in enumerate(results["ads"][:10], 1):
            try:
                ad_id = ad[0]
                a_type = str(ad[1]) if ad[1] else ""
                region = str(ad[2]) if ad[2] else ""
                price = str(ad[3]) if ad[3] else ""
                district = str(ad[4]) if ad[4] else ""
                desc = str(ad[5]) if ad[5] else ""
                qty = str(ad[6]) if ad[6] else ""
                user_id = ad[7] if len(ad) > 7 else None

                # HTML хавфли белгилардан тозалаш
                safe_type = html_module.escape(a_type)
                safe_qty = html_module.escape(qty)
                safe_price = html_module.escape(price)
                safe_region = html_module.escape(region)
                safe_dist = html_module.escape(district)
                safe_desc = html_module.escape(desc)

                text = (
                    f"<b>{i}.</b> <b>{safe_type}</b> — {safe_qty}\n"
                    f"   💰 {safe_price}\n"
                    f"   📍 {safe_region}, {safe_dist}"
                )

                # Эгаси ҳаволаси
                if user_id and int(user_id) > 0:
                    text += (
                        f'   <a href="tg://user?id={user_id}">'
                        f"👤 Эгаси</a>"
                    )
                
                if safe_desc and safe_desc != "Киритилмаган":
                    text += f"   📝 {safe_desc}"

               

                await message.answer(
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

            except Exception as e:
                logging.error(f"Эълон #{i} хато: {e}")
                # Хато бўлса Markdown билан юбориш
                try:
                    safe_text = (
                        f"{i}. {ad[1]} — {ad[6]}\n"
                        f"   💰 {ad[3]}\n"
                        f"   📍 {ad[2]}, {ad[4]}"
                    )
                    await message.answer(safe_text)
                except Exception:
                    pass

    await state.clear()
