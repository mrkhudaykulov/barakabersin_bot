"""
Кўп чатга юбориш (fan-out) учун оқим назорати.

Telegram Bot API'да глобал чеклов бор — тахминан секундига 30 та хабар.
Ундан ошиб кетилса, Telegram 429 (TelegramRetryAfter) қайтаради ва
хабарлар ЙЎҚОЛАДИ, чунки кодда бу оддий "хатолик" сифатида ютиб
юборилар эди.

Бу ердаги `fan_out()` учта муаммони бирданига ҳал қилади:
  • юбориш тезлигини чеклайди (секундига `rate` тадан ошмайди);
  • 429 келса — Telegram айтган вақт кутилиб, ҚАЙТА уринилади;
  • бот блокланган фойдаланувчига (Forbidden) бефойда қайта
    уринилмайди, чунки натижа ҳеч қачон ўзгармайди.
"""

import asyncio
import logging

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

# Telegram'нинг глобал лимити ~30/сония — заҳира билан 25 оламиз.
DEFAULT_RATE = 25
# Бир вақтда очиқ турадиган сўровлар сони (тармоқ кутишини
# параллеллаштириш учун, лимитдан ошмаган ҳолда).
DEFAULT_CONCURRENCY = 8
# 429'дан кейин нечта қайта уриниш.
MAX_RETRIES = 2


class _Pacer:
    """Юборишлар орасида камида 1/rate сония бўлишини таъминлайди."""

    def __init__(self, rate: float):
        self._min_interval = 1.0 / max(rate, 1)
        self._lock = asyncio.Lock()
        self._next_at = 0.0

    async def wait(self):
        async with self._lock:
            now = asyncio.get_running_loop().time()
            start = max(now, self._next_at)
            self._next_at = start + self._min_interval
            delay = start - now
        if delay > 0:
            await asyncio.sleep(delay)


async def fan_out(send, targets, *, rate: float = DEFAULT_RATE,
                  concurrency: int = DEFAULT_CONCURRENCY,
                  description: str = "юбориш"):
    """
    `targets` рўйхатидаги ҳар бир элемент учун `send(target)` ни
    чақиради. Натижалар рўйхатини — тартибни сақлаган ҳолда — қайтаради:
    муваффақиятли бўлса `send()` нима қайтарган бўлса ўша, акс ҳолда None.

    `send` — битта аргумент қабул қиладиган async функция.
    """
    if not targets:
        return []

    pacer = _Pacer(rate)
    semaphore = asyncio.Semaphore(concurrency)

    async def _send_one(target):
        async with semaphore:
            for attempt in range(MAX_RETRIES + 1):
                await pacer.wait()
                try:
                    return await send(target)
                except TelegramRetryAfter as e:
                    # Лимитга урилдик — Telegram айтган вақтни кутамиз.
                    if attempt >= MAX_RETRIES:
                        logging.warning(
                            "%s: лимит (429) такрорланди, воз кечилди (target=%r)",
                            description, target
                        )
                        return None
                    logging.info(
                        "%s: лимит (429) — %s сония кутилмоқда...",
                        description, e.retry_after
                    )
                    await asyncio.sleep(e.retry_after + 1)
                except TelegramForbiddenError:
                    # Фойдаланувчи ботни блоклаган ёки чатдан чиқарган —
                    # қайта уриниш натижани ўзгартирмайди.
                    logging.info("%s: қабул қилувчи ботни блоклаган (target=%r)",
                                 description, target)
                    return None
                except Exception as e:
                    logging.warning("%s: хатолик (target=%r): %s", description, target, e)
                    return None
            return None

    return await asyncio.gather(*[_send_one(t) for t in targets])
