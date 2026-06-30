from aiogram.fsm.state import State, StatesGroup


class AdStates(StatesGroup):
    photo = State()
    animal_type = State()
    region = State()
    district = State()
    mfy = State()
    quantity = State()
    price = State()
    description = State()
    phone = State()


class CalcStates(StatesGroup):
    menu = State()
    qoy_bosh = State()
    qoy_narx = State()
    qoy_qozi_narx = State()
    qoy_em_narx = State()
    qm_bosh = State()
    qm_yon = State()
    qm_sut_vazn = State()
    qm_narx = State()
    qm_em_narx = State()


class MarketStates(StatesGroup):
    """
    Бирлаштирилган '📊 Бозор таҳлили' бўлими учун субменю ҳолати.
    Бу ҳолатда: Нархлар индекси, Ферма калькулятори тугмалари кутилади.
    """
    menu = State()


class PriceIndexStates(StatesGroup):
    """'Нархлар индекси' ичидаги ҳолат (prices.py учун)."""
    menu = State()


class SearchStates(StatesGroup):
    animal_type = State()
    region = State()
    district = State()

class PriceInputStates(StatesGroup):
    animal_type = State()
    region = State()
    price = State()


class NotifyStates(StatesGroup):
    """'🔔 Хабардор қил' бўлими — кузатув яратиш ва бошқариш."""
    menu = State()
    animal_type = State()
    region = State()
    district = State()
    min_price = State()
    max_price = State()
    edit_min_price = State()
    edit_max_price = State()


class AdminStates(StatesGroup):
    """Админ панели ҳолатлари."""
    menu = State()

    # Эълонлар
    ads_menu = State()
    del_ad_id = State()
    del_user_ads_id = State()

    # Нархлар
    prices_menu = State()
    add_price_animal = State()
    add_price_region = State()
    add_price_value = State()
    add_multi_text = State()
    del_price_id = State()
    del_animal_name = State()
    del_region_name = State()

    # Блок
    block_menu = State()
    unblock_id = State()

    # Премиум
    premium_menu = State()
    premium_give_id = State()
    premium_remove_id = State()

    # Тарқатиш
    broadcast_text = State()


class VetStates(StatesGroup):
    """
    'Ветеринария' бўлими — вилоят ва туман танлаб,
    ўша ҳудуд ветеринария мутахассиси контактини олиш.
    """
    region = State()
    district = State()


class VetSuggestStates(StatesGroup):
    """
    Фойдаланувчи ветеринария ходими ҳақида таклиф киритиши
    (янги қўшиш ёки мавжудини ўзгартириш).
    Вилоят/туман контакт кўрсатилган контекстдан олинади.
    """
    action_type = State()      # "Янги қўшиш" ёки "Ўзгартириш"
    role_type = State()        # "Бўлим бошлиғи" ёки "Лаборатория мудири"
    fish = State()
    lavozim = State()
    tel = State()
    comment = State()
    confirm = State()


class VetAdminStates(StatesGroup):
    """
    Админ учун — кутилаётган ветеринария таклифларини
    бирма-бир кўриб чиқиш ва тасдиқлаш/рад этиш.
    """
    reviewing = State()
    reject_comment = State()
