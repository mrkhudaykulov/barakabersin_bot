from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Эълон бериш"), KeyboardButton(text="🔍 Эълон қидириш")],
        [KeyboardButton(text="📊 Нархлар индекси"), KeyboardButton(text="🗂 Менинг эълонларим")],
        [KeyboardButton(text="🧮 Ферма калькулятори"), KeyboardButton(text="🔔 Хабардор қил")]
              
    ], resize_keyboard=True)


def calc_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🐑 Қўй калькулятори"), KeyboardButton(text="🐄 Қорамол калькулятори")],
        [KeyboardButton(text="🏠 Бош меню")]
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


def animal_types_keyboard():
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
    return builder.as_markup(resize_keyboard=True)


def regions_keyboard():
    builder = ReplyKeyboardBuilder()
    regions = [
        "Қашқадарё", "Сурхондарё", "Тошкент", "Фарғона",
        "Андижон", "Наманган", "Самарқанд", "Бухоро",
        "Навоий", "Жиззах", "Сирдарё", "Хоразм",
        "Қорақалпоғистон"
    ]
    for r in regions:
        builder.add(KeyboardButton(text=r))
    builder.adjust(2)
    builder.row(
        KeyboardButton(text="🔙 Орқага"),
        KeyboardButton(text="❌ Бекор қилиш")
    )
    return builder.as_markup(resize_keyboard=True)


def districts_keyboard(region):
    builder = ReplyKeyboardBuilder()

    districts = {
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

    list_d = districts.get(region, ["Марказ тумани", "Чет тумани"])

    for d in list_d:
        builder.add(KeyboardButton(text=d))
    builder.adjust(3)
    builder.row(
        KeyboardButton(text="🔙 Орқага"),
        KeyboardButton(text="❌ Бекор қилиш")
    )
    return builder.as_markup(resize_keyboard=True)


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


def phone_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Рақамни юбориш", request_contact=True)],
        step_navigation()
    ], resize_keyboard=True)


def price_index_keyboard():
    builder = ReplyKeyboardBuilder()
    types_list = [
        "🐄 Буқа/Сигир", "🐑 Қўй", "🐴 От",
        "🐐 Эчки", "🐫 Туя", "🐓 Парранда"
    ]
    for t in types_list:
        builder.add(KeyboardButton(text=t))
    builder.adjust(3)
    builder.row(
        KeyboardButton(text="📊 Барчаси"),
        KeyboardButton(text="💰 Нарх киритиш")        
    )
    builder.row(KeyboardButton(text="🏠 Бош меню"))       
    return builder.as_markup(resize_keyboard=True)


def search_animal_keyboard():
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
    return builder.as_markup(resize_keyboard=True)


def regions_with_all_keyboard():
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
    return builder.as_markup(resize_keyboard=True)


def notify_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Янги кузатув")],
            [KeyboardButton(text="📌 Менинг кузатувларим")],
            [KeyboardButton(text="🏠 Бош меню")]
        ],
        resize_keyboard=True
    )

def notification_districts_keyboard(region_text):
    """Хабардорлик учун туманлар — танланган вилоят бўйича + Барчаси"""
    
    # 1. Тепадаги districts_keyboard функцияси ичидаги луғатдан 
    # хатосиз нусха олиш учун 'districts_list' номидан фойдаланамиз
    districts_list = districts_keyboard(region_text).keyboard
    
    # Бу ердан навигация тугмаларини олиб ташлаб, фақат соф туман номларини ажратамиз
    clean_districts = []
    for row in districts_list:
        for button in row:
            if button.text not in ["🔙 Орқага", "❌ Бекор қилиш"]:
                clean_districts.append(button.text)

    buttons = []
    # Аввал "Барчаси" тугмаси
    buttons.append([KeyboardButton(text="📍 Барчаси")])

    # Кейин тозаланган туманлар — 2 тадан қаторга солинади
    for i in range(0, len(clean_districts), 2):
        row = [KeyboardButton(text=clean_districts[i])]
        if i + 1 < len(clean_districts):
            row.append(KeyboardButton(text=clean_districts[i + 1]))
        buttons.append(row)

    # Охирда орқага
    buttons.append([KeyboardButton(text="🔙 Орқага")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
