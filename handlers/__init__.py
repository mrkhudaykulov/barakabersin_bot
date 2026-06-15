from aiogram import Dispatcher

from handlers import navigation, ads, search, prices, admin, calculators, notify


def register_all_handlers(dp: Dispatcher):
    """
    Барча handler routerларини асосий Dispatcher га улайди.
    Тартиб МУҲИМ — navigation энг аввал бўлиши шарт
    (cancel/back handlerлари бошқа handlerлардан олдин ишлаши керак).
    """
    dp.include_router(navigation.router)
    dp.include_router(calculators.router)
    dp.include_router(prices.router)
    dp.include_router(search.router)
    dp.include_router(ads.router)
    dp.include_router(admin.router)
    dp.include_router(notify.router)
