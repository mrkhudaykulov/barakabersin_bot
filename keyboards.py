import logging
from functools import lru_cache

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def _layout_of(builder: ReplyKeyboardBuilder):
    """Builder натижасини оддий матн жадвалига (tuple) айлантиради."""
    markup = builder.as_markup()
    return tuple(tuple(btn.text for btn in row) for row in markup.keyboard)


def _markup(layout):
    """
    Кэшланган матн жадвалидан ҲАР САФАР ЯНГИ клавиатура объекти қуради.

    Нима учун объектнинг ўзи кэшланмайди: клавиатура объекти ўзгарувчан
    (mutable) — агар кимдир унга тугма қўшса, ўша тугма кэшдан фойдаланган
    БАРЧА фойдаланувчиларга кўриниб кетарди (масалан гуруҳ админи
    тугмалари ҳаммага). Шунинг учун фақат матнлар кэшланади, объект эса
    ҳар доим янги.
    """
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in layout],
        resize_keyboard=True
    )

# Вилоятлар рўйхати — клавиатура ҳам, киритилган матнни текшириш
# (валидация) ҳам шу битта манбадан фойдаланиши учун модул даражасида.
REGIONS = [
    "Қашқадарё", "Сурхондарё", "Тошкент", "Фарғона",
    "Андижон", "Наманган", "Самарқанд", "Бухоро",
    "Навоий", "Жиззах", "Сирдарё", "Хоразм",
    "Қорақалпоғистон"
]

DISTRICTS = {
    "Фарғона": [
        "Бешариқ", "Боғдод", "Бувайда", "Данғара", "Ёзёвон",
        "Қува", "Қувасой", "Қўқон", "Қўштепа", "Марғилон",
        "Олтиариқ", "Риштон", "Сўх", "Тошлоқ", "Ўзбекистон",
        "Учкўприк", "Фарғона", "Фурқат"
    ],
    "Тошкент": [
        "Пойтахт", "Ангрен", "Бекобод", "Бўка", "Бўстонлиқ",
        "Зангиота", "Қибрай", "Қуйичирчиқ", "Оққўрғон", "Олмалиқ",
        "Оҳангарон", "Паркент", "Пискент", "Тошкент.т",
        "Ўртачирчиқ", "Чиноз", "Чирчиқ", "Юқоричирчиқ", "Ягийўл", "Нурафшон"
    ],
    "Қашқадарё": [
        "Ғузор", "Деҳқонобод", "Касби", "Китоб", "Косон",
        "Қамаши", "Қарши", "Миришкор", "Чироқчи", "Нишон",
        "Кўкдала", "Яккабоғ", "Шаҳрисабз", "Муборак"
    ],
    "Наманган": [
        "Косонсой", "Мингбулоқ", "Наманган", "Норин", "Поп",
        "Тўрақўрғон", "Уйчи", "Учқўрғон", "Чортоқ",
        "Чуст", "Янгиқўрғон", "Давлатобод"
    ],
    "Андижон": [
        "Андижон", "Асака", "Балиқчи", "Бўстон", "Булоқбоши",
        "Жалақудуқ", "Избоскан", "Қўрғонтепа", "Марҳамат",
        "Олтинкўл", "Пахтобод", "Улуғнор", "Хонобод", "Хўжаобод", "Шаҳрихон"
    ],
    "Бухоро": [
        "Бухоро", "Вобкент", "Ғиждувон", "Жондор", "Когон",
        "Қоровулбозор", "Қоракўл", "Олот", "Пешку", "Ромитан", "Шофиркон"
    ],
    "Жиззах": [
        "Арнасой", "Бахмал", "Ғаллаорол", "Дўстлик", "Жиззах",
        "Зарбдор", "Зафаробод", "Зомин", "Мирзачўл",
        "Пахтакор", "Фориш", "Ш.Рашидов", "Янгиобод"
    ],
    "Қорақалпоғистон": [
        "Амударё", "Беруний", "Бўзатов", "Кегейли", "Қонликўл",
        "Қораўзак", "Қўнғирот", "Мўйноқ", "Нукус", "Тахиатош",
        "Тахтакўпир", "Тўрткўл", "Хўжайли", "Чимбой", "Шуманай", "Элликқала"
    ],
    "Навоий": [
        "Зарафшон", "Кармана", "Конимех", "Қизилтепа",
        "Навбаҳор", "Навоий", "Нурота", "Томди",
        "Учқудуқ", "Хатирчи", "Ғазғон"
    ],
    "Самарқанд": [
        "Булунғур", "Жомбой", "Иштихон", "Каттақўрғон",
        "Қўшработ", "Нарпай", "Нуробод", "Оқдарё", "Пахтачи",
        "Пайариқ", "Пасдарғом", "Самарқанд", "Тойлоқ", "Ургут"
    ],
    "Сирдарё": [
        "Боёвут", "Гулистон", "Мирзаобод", "Оқолтин",
        "Сайхунобод", "Сардоба", "Сирдарё", "Ховос", "Ширин", "Янгиер"
    ],
    "Сурхондарё": [
        "Ангор", "Бандихон", "Бойсун", "Денов", "Жарқўрғон",
        "Қизириқ", "Қумқўрғон", "Музработ", "Олтинсой",
        "Сариосиё", "Термиз", "Узун", "Шеробод", "Шўрчи"
    ],
    "Хоразм": [
        "Боғот", "Гурлан", "Қўшкўпир", "Урганч", "Хазорасп",
        "Хива", "Хонқа", "Шовот", "Янгиариқ", "Янгибозор", "Тупроққала"
    ]
}


def main_menu():
    # ⚠️ "🌐 Тез эълон бериш" тугмаси аввал шу ерда эди — Mini App'ни
    # энди Telegram'нинг ЧАТ МЕНЮ тугмаси (хабар қутиси ёнидаги, main.py
    # setup_bot_commands'да "Эълон" деб созланган) очади, шунинг учун
    # менюда такрор тугма шарт эмас.
    buttons = [
        [KeyboardButton(text="➕ Эълон бериш"), KeyboardButton(text="🔍 Эълон қидириш")],
        [KeyboardButton(text="📊 Бозор таҳлили"), KeyboardButton(text="🗂 Менинг эълонларим")],
        [KeyboardButton(text="🩺 Ветеринария"), KeyboardButton(text="🔔 Хабардор қил")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    


def market_analysis_menu():
    """
    Бирлаштирилган '📊 Бозор таҳлили' бўлими:
    Нархлар индекси + Ферма калькулятори
    """
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Нархлар индекси")],
        [KeyboardButton(text="🧮 Ферма калькулятори")],
        [KeyboardButton(text="🏠 Бош меню")]
    ], resize_keyboard=True)


def calc_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🐑 Қўй калькулятори"), KeyboardButton(text="🐄 Қорамол калькулятори")],
        [KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="🏠 Бош меню")]
    ], resize_keyboard=True)


def calc_qoramol_direction_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🥛 Сут"), KeyboardButton(text="🥩 Гўшт")],
        [KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="❌ Бекор қилиш")]
    ], resize_keyboard=True)


def step_navigation():
    return [KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="❌ Бекор қилиш")]


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Бекор қилиш")]],
        resize_keyboard=True
    )


def photo_confirm_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📥 Расмларни тасдиқлаш")],
        step_navigation()
    ], resize_keyboard=True)


@lru_cache(maxsize=1)
def _animal_types_layout():
    builder = ReplyKeyboardBuilder()
    types_list = [
        "Буқа", "Сигир", "Тана", "Бузоқ", "Қўчқор",
        "Совлиқ", "Қўзи", "Эчки", "Улоқ", "От",
        "Туя", "Парранда", "Бошқа"
    ]
    for t in types_list:
        builder.add(KeyboardButton(text=t))
    builder.adjust(3)
    builder.row(
        KeyboardButton(text="🔙 Орқага"),
        KeyboardButton(text="❌ Бекор қилиш")
    )
    return _layout_of(builder)


def animal_types_keyboard():
    return _markup(_animal_types_layout())


@lru_cache(maxsize=1)
def _regions_layout():
    builder = ReplyKeyboardBuilder()
    for r in REGIONS:
        builder.add(KeyboardButton(text=r))
    builder.adjust(2)
    builder.row(
        KeyboardButton(text="🔙 Орқага"),
        KeyboardButton(text="❌ Бекор қилиш")
    )
    return _layout_of(builder)


def regions_keyboard():
    return _markup(_regions_layout())


@lru_cache(maxsize=64)
def _districts_layout(region):
    builder = ReplyKeyboardBuilder()
    list_d = DISTRICTS.get(region)
    if list_d is None:
        # Бу ҳолат маълумотдаги камчиликни билдиради (нотўғри/эски вилоят
        # номи) — жимгина сохта туманлар кўрсатиш ўрнига логга ёзамиз,
        # акс ҳолда фойдаланувчи ҳеч нарса топилмайдиган кўчага киради.
        logging.warning("districts_keyboard: '%s' вилояти DISTRICTS'да йўқ!", region)
        list_d = ["Марказ тумани", "Чет тумани"]

    for d in list_d:
        builder.add(KeyboardButton(text=d))
    builder.adjust(3)
    builder.row(
        KeyboardButton(text="🔙 Орқага"),
        KeyboardButton(text="❌ Бекор қилиш")
    )
    return _layout_of(builder)


def districts_keyboard(region):
    return _markup(_districts_layout(region))


def standard_step_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[step_navigation()],
        resize_keyboard=True
    )


def description_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⏭ Ёзмасдан ўтказиб юбориш")],
        step_navigation()
    ], resize_keyboard=True)


SKIP_PASSPORT_TEXT = "⏭ Паспортсиз давом этиш"


def passport_keyboard():
    """Ҳайвон паспорти қадами — рақам ихтиёрий, ўтказиб юборса бўлади."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=SKIP_PASSPORT_TEXT)],
        step_navigation()
    ], resize_keyboard=True)


def phone_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Рақамни юбориш", request_contact=True)],
        step_navigation()
    ], resize_keyboard=True)


@lru_cache(maxsize=1)
def _price_index_layout():
    builder = ReplyKeyboardBuilder()
    types_list = [
        "🐂 Буқа", "🐄 Сигир", "🐮 Тана", "🐮 Бузоқ",
        "🐏 Қўчқор", "🐑 Совлиқ", "🐑 Қўзи",
        "🐐 Эчки", "🐐 Улоқ", "🐴 От",
        "🐫 Туя", "🐓 Парранда"
    ]
    for t in types_list:
        builder.add(KeyboardButton(text=t))
    builder.adjust(3)
    builder.row(
        KeyboardButton(text="📊 Барчаси"),
        KeyboardButton(text="💰 Нарх киритиш")
    )
    builder.row(
        KeyboardButton(text="🔙 Орқага"),
        KeyboardButton(text="🏠 Бош меню")
    )
    return _layout_of(builder)


def price_index_keyboard():
    return _markup(_price_index_layout())


@lru_cache(maxsize=1)
def _search_animal_layout():
    builder = ReplyKeyboardBuilder()
    types_list = [
        "Буқа", "Сигир", "Тана", "Бузоқ",
        "Қўчқор", "Совлиқ", "Қўзи", "Эчки",
        "От", "Туя", "Парранда", "Барчаси"
    ]
    for t in types_list:
        builder.add(KeyboardButton(text=t))
    builder.adjust(3)
    builder.row(
        KeyboardButton(text="🔙 Орқага"),
        KeyboardButton(text="❌ Бекор қилиш")
    )
    return _layout_of(builder)


def search_animal_keyboard():
    return _markup(_search_animal_layout())


@lru_cache(maxsize=1)
def _regions_with_all_layout():
    builder = ReplyKeyboardBuilder()
    regions = [
        "Барчаси", "Қашқадарё", "Сурхондарё", "Тошкент",
        "Фарғона", "Андижон", "Наманган", "Самарқанд",
        "Бухоро", "Навоий", "Жиззах", "Сирдарё",
        "Хоразм", "Қорақалпоғистон"
    ]
    for r in regions:
        builder.add(KeyboardButton(text=r))
    builder.adjust(2)
    builder.row(
        KeyboardButton(text="🔙 Орқага"),
        KeyboardButton(text="❌ Бекор қилиш")
    )
    return _layout_of(builder)


def regions_with_all_keyboard():
    return _markup(_regions_with_all_layout())


def notify_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Янги кузатув")],
            [KeyboardButton(text="📌 Менинг кузатувларим")],
            [KeyboardButton(text="🏠 Бош меню")]
        ],
        resize_keyboard=True
    )

@lru_cache(maxsize=64)
def _notification_districts_layout(region):
    builder = ReplyKeyboardBuilder()

    # Туманлар
    list_d = DISTRICTS.get(region, [])
    for d in list_d:
        builder.add(KeyboardButton(text=d))
    
    # "Барчаси" tugmasi
    builder.add(KeyboardButton(text="📍 Барчаси"))
    
    # Orqaga va Bekor qilish tugmalari
    builder.add(KeyboardButton(text="🔙 Орқага"))
    builder.add(KeyboardButton(text="❌ Бекор қилиш"))

    builder.adjust(2)  # Har bir qatorda 2 tadan

    return _layout_of(builder)


def notification_districts_keyboard(region):
    """Хабардорлик учун туманлар — вилоят бўйича + Барчаси"""
    return _markup(_notification_districts_layout(region))


#  Админ бошқариш панели
def main_menu_admin():
    """Админ учун бош меню"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Эълон бериш"), KeyboardButton(text="🔍 Эълон қидириш")],
        [KeyboardButton(text="📊 Бозор таҳлили"), KeyboardButton(text="🗂 Менинг эълонларим")],
        [KeyboardButton(text="🩺 Ветеринария"), KeyboardButton(text="🔔 Хабардор қил")],
        [KeyboardButton(text="🔐 Админ панел")]
    ], resize_keyboard=True)
    
def admin_menu_keyboard():
    """Админ асосий менюси"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Эълонлар"), KeyboardButton(text="💰 Нархлар")],
        [KeyboardButton(text="🚫 Блок"), KeyboardButton(text="💎 Премиум")],
        [KeyboardButton(text="📢 Тарқатиш"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🔍 Нарх текшириш"), KeyboardButton(text="🩺 Вет таклифлар")],
        [KeyboardButton(text="🏘 Уланган гуруҳлар"), KeyboardButton(text="/reviewadmins")],
        [KeyboardButton(text="🏠 Бош меню")]
    ], resize_keyboard=True)


def admin_ads_keyboard():
    """Эълонлар бошқариши"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👁 Эълонларни кўриш")],
        [KeyboardButton(text="🗑 ID бўйича ўчириш")],
        [KeyboardButton(text="🗑 Фойдаланувчи эълонларини ўчириш")],
        [KeyboardButton(text="🔙 Орқага")]
    ], resize_keyboard=True)


def admin_prices_keyboard():
    """Нархлар бошқариши"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Нарх қўшиш"), KeyboardButton(text="➕ Кўп нарх қўшиш")],
        [KeyboardButton(text="👁 Нархларни кўриш")],
        [KeyboardButton(text="🗑 Нархни ўчириш ID"), KeyboardButton(text="🗑 Ҳайвон бўйича ўчириш")],
        [KeyboardButton(text="🗑 Вилоят бўйича ўчириш"), KeyboardButton(text="🗑 Барчасини ўчириш")],
        [KeyboardButton(text="🔙 Орқага")]
    ], resize_keyboard=True)


def admin_block_keyboard():
    """Блок бошқариши"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚫 Блокланганлар рўйхати")],
        [KeyboardButton(text="🔓 Блокдан чиқариш")],
        [KeyboardButton(text="🔙 Орқага")]
    ], resize_keyboard=True)


def admin_premium_keyboard():
    """Премиум бошқариши"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💎 Премиум бериш")],
        [KeyboardButton(text="❌ Премиум олиш")],
        [KeyboardButton(text="💎 Премиум рўйхати")],
        [KeyboardButton(text="🔙 Орқага")]
    ], resize_keyboard=True)


# ═══════════════════════════════════════
# ВЕТЕРИНАРИЯ ТАКЛИФ КЕЙБОАРДЛАРИ
# ═══════════════════════════════════════

def vet_contact_result_keyboard():
    """Контакт кўрсатилгандан кейинги тугмалар — таклиф қилиш имкони."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Маълумотга таклиф киритиш")],
        [KeyboardButton(text="🔙 Орқага"), KeyboardButton(text="🏠 Бош меню")]
    ], resize_keyboard=True)


def vet_action_type_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🆕 Янги ходим қўшиш")],
        [KeyboardButton(text="✏️ Мавжудини ўзгартириш")],
        step_navigation()
    ], resize_keyboard=True)


def vet_role_type_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🏢 Бўлим бошлиғи")],
        [KeyboardButton(text="🔬 Лаборатория мудири")],
        step_navigation()
    ], resize_keyboard=True)


def vet_comment_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⏭ Изоҳсиз ўтказиб юбориш")],
        step_navigation()
    ], resize_keyboard=True)


def vet_confirm_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✅ Таклифни юбориш")],
        step_navigation()
    ], resize_keyboard=True)


def vet_admin_review_keyboard():
    """Админ кутилаётган таклифни кўриб чиқишда ишлатадиган тугмалар."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✅ Тасдиқлаш"), KeyboardButton(text="❌ Рад этиш")],
        [KeyboardButton(text="✏️ Таҳрирлаш"), KeyboardButton(text="⏭ Кейингисига ўтиш")],
        [KeyboardButton(text="🏠 Бош меню")]
    ], resize_keyboard=True)


def vet_admin_edit_keyboard():
    """Таҳрирлаш вақтида — қайси майдонни ўзгартириш."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Ф.И.Ш"), KeyboardButton(text="💼 Лавозим")],
        [KeyboardButton(text="📞 Телефон")],
        [KeyboardButton(text="✅ Таҳрирни сақлаш")],
        [KeyboardButton(text="🔙 Орқага")]
    ], resize_keyboard=True)


def vet_admin_edit_field_keyboard():
    """Битта майдонни киритиш вақтидаги тугма."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔙 Орқага")]
    ], resize_keyboard=True)
