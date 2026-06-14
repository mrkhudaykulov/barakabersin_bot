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


class PriceInputStates(StatesGroup):
    animal_type = State()
    region = State()
    price = State()
    
