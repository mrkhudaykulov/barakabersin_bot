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


class SearchStates(StatesGroup):
    animal_type = State()
    region = State()
    district = State()


class PriceInputStates(StatesGroup):
    animal_type = State()
    region = State()
    price = State()
    district = State()
    

class NotifyStates(StatesGroup):
    animal_type = State()
    region = State()
    district = State()
    min_price = State()
    max_price = State()
    edit_min_price = State()
    edit_max_price = State()


class AdminStates(StatesGroup):
    menu = State()
    ads_menu = State()
    prices_menu = State()
    block_menu = State()
    premium_menu = State()
    # Нарх қўшиш
    add_price_animal = State()
    add_price_region = State()
    add_price_value = State()
    add_multi_text = State()
    del_price_id = State()
    del_animal_name = State()
    del_region_name = State()
    del_ad_id = State()
    del_user_ads_id = State()
    unblock_id = State()
    premium_give_id = State()
    premium_remove_id = State()
    broadcast_text = State()
