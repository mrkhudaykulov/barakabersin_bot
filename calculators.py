# calculators.py

def fmt(n):
    return f"{round(n):,}".replace(",", " ")

def qoy_hisobla(ona, narx, qozi_narx, em_kg):
    jami = round(ona * 1.1)
    r_ona_s  = round(ona * 0.3)
    r_ona  = r_ona_s * narx
    r_qozi_s = round(ona * 1.5)
    r_qozi = r_qozi_s * qozi_narx
    r_jun    = jami * 25_000
    kass     = round(ona * 0.05)
    r_gosh   = kass * 35 * 50_000
    r_total  = r_ona + r_qozi + r_jun + r_gosh

    x_pich  = jami * 200 * 1_200
    x_em    = jami * 50 * em_kg
    x_vet   = jami * 150_000
    x_chop  = 3_600_000 if ona >= 10 else 0
    x_kom   = jami * 80_000
    x_bosh  = round(r_total * 0.05)
    x_total = x_pich + x_em + x_vet + x_chop + x_kom + x_bosh

    sof  = r_total - x_total
    rent = round((sof / x_total) * 100) if x_total else 0
    fe = "✅" if sof >= 0 else "❌"
    re = "🟢" if rent >= 20 else ("🟡" if rent >= 0 else "🔴")

    return (
        f"🐑 *Қўй боқиш — йиллик ҳисоб*\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Умумий:* {ona} Қўй + {jami} жами бош\n\n"
        f"📈 *Даромадлар*\n"
        f"• Қўй сотиш ({r_ona_s} бош): `{fmt(r_ona)}` сўм\n"
        f"• Қўзи ({r_qozi_s} та): `{fmt(r_qozi)}` сўм\n"
        f"• Жун ({jami} кг): `{fmt(r_jun)}` сўм\n"
        f"• Гўшт ({kass} бош): `{fmt(r_gosh)}` сўм\n"
        f"▸ *Жами: `{fmt(r_total)}` сўм*\n\n"
        f"📉 *Харажатлар*\n"
        f"• Пичан: `{fmt(x_pich)}` сўм\n"
        f"• Ем: `{fmt(x_em)}` сўм\n"
        f"• Ветеринария: `{fmt(x_vet)}` сўм\n"
        f"• Чўпон: `{fmt(x_chop)}` сўм\n"
        f"• Коммунал: `{fmt(x_kom)}` сўм\n"
        f"• Бошқа: `{fmt(x_bosh)}` сўм\n"
        f"▸ *Жами: `{fmt(x_total)}` сўм*\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{fe} *Соф фойда: `{fmt(sof)}` сўм/йил*\n"
        f"💰 Ойлик: `{fmt(sof//12)}` сўм\n"
        f"{re} Фойда ёки зарар фоизи (Рентабеллик): *{rent}%*\n\n"
        f"📌 _Натижалар тахминий._"
    )

def qm_hisobla_sut(bosh, kun_sut_l, sut_narx, em_kg):
    jami = round(bosh * 1.05)
    r_sut    = bosh * kun_sut_l * 300 * sut_narx
    buz_soni = bosh
    r_buzoq  = buz_soni * 1_500_000
    kass     = round(bosh * 0.05)
    r_gosh   = kass * 400 * 25_000
    r_total  = r_sut + r_buzoq + r_gosh

    x_pich  = jami * 2_500 * 1_200
    x_silo  = jami * 3_000 * 300
    x_em    = jami * 800 * em_kg
    x_vet   = jami * 500_000
    x_chop  = 7_200_000 if bosh >= 5 else 0
    x_kom   = jami * 200_000
    x_bosh  = round(r_total * 0.05)
    x_total = x_pich + x_silo + x_em + x_vet + x_chop + x_kom + x_bosh

    sof  = r_total - x_total
    rent = round((sof / x_total) * 100) if x_total else 0
    fe = "✅" if sof >= 0 else "❌"
    re = "🟢" if rent >= 15 else ("🟡" if rent >= 0 else "🔴")

    return (
        f"🐄 *Қорамол (сут) — йиллик ҳисоб*\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Умумий:* {bosh} сигир, {jami} жами бош\n"
        f"🥛 Лактация: {kun_sut_l} л/кун × 300 кун\n\n"
        f"📈 *Даромадлар*\n"
        f"• Сут ({bosh*kun_sut_l*300:,} л): `{fmt(r_sut)}` сўм\n"
        f"• Бузоқ ({buz_soni} та): `{fmt(r_buzoq)}` сўм\n"
        f"• Гўшт кассация ({kass} бош): `{fmt(r_gosh)}` сўм\n"
        f"▸ *Жами: `{fmt(r_total)}` сўм*\n\n"
        f"📉 *Харажатлар*\n"
        f"• Пичан: `{fmt(x_pich)}` сўм\n"
        f"• Силос: `{fmt(x_silo)}` сўм\n"
        f"• Комбикорм: `{fmt(x_em)}` сўм\n"
        f"• Ветеринария: `{fmt(x_vet)}` сўм\n"
        f"• Чорвадор: `{fmt(x_chop)}` сўм\n"
        f"• Коммунал: `{fmt(x_kom)}` сўм\n"
        f"• Бошқа: `{fmt(x_bosh)}` сўм\n"
        f"▸ *Жами: `{fmt(x_total)}` сўм*\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{fe} *Соф фойда: `{fmt(sof)}` сўм/йил*\n"
        f"💰 Ойлик: `{fmt(sof//12)}` сўм\n"
        f"{re} Фойда ёки зарар фоизи (Рентабеллик): *{rent}%*\n\n"
        f"📌 _Натижалар тахминий._"
    )

def qm_hisobla_gosht(bosh, vazn, narx_kg, em_kg):
    jami = round(bosh * 1.05)
    sotish   = round(bosh * 0.35)
    r_gosh   = sotish * vazn * narx_kg
    buz_soni = bosh
    r_buzoq  = buz_soni * 1_500_000
    r_total  = r_gosh + r_buzoq

    x_pich  = jami * 2_500 * 1_200
    x_silo  = jami * 3_000 * 300
    x_em    = jami * 800 * em_kg
    x_vet   = jami * 400_000
    x_chop  = 7_200_000 if bosh >= 5 else 0
    x_kom   = jami * 150_000
    x_bosh  = round(r_total * 0.05)
    x_total = x_pich + x_silo + x_em + x_vet + x_chop + x_kom + x_bosh

    sof  = r_total - x_total
    rent = round((sof / x_total) * 100) if x_total else 0
    fe = "✅" if sof >= 0 else "❌"
    re = "🟢" if rent >= 15 else ("🟡" if rent >= 0 else "🔴")

    return (
        f"🐄 *Қорамол (гўшт) — йиллик ҳисоб*\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Умумий:* {bosh} Сигир, {jami} жами бош\n"
        f"🥩 Сотиш: {sotish} бош × {vazn} кг × {fmt(narx_kg)} сўм/кг\n\n"
        f"📈 *Даромадлар*\n"
        f"• Гўшт ({sotish} бош): `{fmt(r_gosh)}` сўм\n"
        f"• Бузоқ ({buz_soni} та): `{fmt(r_buzoq)}` сўм\n"
        f"▸ *Жами: `{fmt(r_total)}` сўм*\n\n"
        f"📉 *Харажатлар*\n"
        f"• Пичан: `{fmt(x_pich)}` сўм\n"
        f"• Силос: `{fmt(x_silo)}` сўм\n"
        f"• Комбикорм: `{fmt(x_em)}` сўм\n"
        f"• Ветеринария: `{fmt(x_vet)}` сўм\n"
        f"• Чорвадор: `{fmt(x_chop)}` сўм\n"
        f"• Коммунал: `{fmt(x_kom)}` сўм\n"
        f"• Бошқа: `{fmt(x_bosh)}` сўм\n"
        f"▸ *Жами: `{fmt(x_total)}` сўм*\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{fe} *Соф фойда: `{fmt(sof)}` сўм/йил*\n"
        f"💰 Ойлик: `{fmt(sof//12)}` сўм\n"
        f"{re} Фойда ёки зарар фоизи (Рентабеллик): *{rent}%*\n\n"
        f"📌 _Натижалар тахминий._"
    )
