"""
scheduler.py — планировщик автоматического обновления официальных вакансий.

Запускает run_all_parsers() при старте бота и каждые INTERVAL_HOURS часов.
Для каждой новой вакансии находит подходящих подписчиков и отправляет уведомление.
"""

import threading
import logging

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from official_parser import run_all_parsers

logger = logging.getLogger(__name__)

INTERVAL_HOURS = 6


def _notify_subscriber(bot, user_id: int, vac: dict) -> None:
    """Отправляет уведомление о новой официальной вакансии одному подписчику."""
    text = (
        "🆕 *Новая вакансия*\n\n"
        "🟢 Официальный источник\n\n"
        f"🏢 Компания: {vac.get('company_name', '—')}\n"
        f"👷 Профессия: {vac.get('profession', '—')}\n"
        f"📍 Город: {vac.get('city', '—')}\n"
        f"💰 Зарплата: {vac.get('salary') or '—'}\n"
        f"⛺ График: {vac.get('schedule') or '—'}"
    )
    markup = InlineKeyboardMarkup()
    if vac.get('source_url'):
        markup.add(InlineKeyboardButton("🌐 Открыть оригинал", url=vac['source_url']))
    try:
        bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.warning("Не удалось уведомить пользователя %s: %s", user_id, e)


def run_parser_cycle(bot) -> None:
    """Один цикл: запуск всех парсеров + уведомление подписчиков о новых вакансиях."""
    # atlas_mining_parser регистрирует себя в PARSERS при импорте;
    # повторный импорт безопасен — Python кэширует модули.
    import atlas_mining_parser  # noqa: F401

    logger.info("[Scheduler] Запуск цикла обновления официальных вакансий...")
    results = run_all_parsers()

    total_new = sum(r.get("saved", 0) for r in results)
    logger.info("[Scheduler] Новых вакансий за цикл: %d", total_new)

    for result in results:
        for vac in result.get("new_vacancies", []):
            subscribers = db.find_matching_subscribers(
                profession=vac.get("profession", ""),
                city=vac.get("city", ""),
            )
            for uid in subscribers:
                _notify_subscriber(bot, uid, vac)


def _scheduler_loop(bot) -> None:
    """Фоновый поток: запускается сразу, затем повторяет каждые INTERVAL_HOURS часов."""
    import time
    while True:
        try:
            run_parser_cycle(bot)
        except Exception as e:
            logger.error("[Scheduler] Необработанная ошибка в цикле: %s", e)
        logger.info("[Scheduler] Следующий запуск через %d ч.", INTERVAL_HOURS)
        time.sleep(INTERVAL_HOURS * 3600)


def start_scheduler(bot) -> None:
    """Запускает планировщик в фоновом daemon-потоке."""
    t = threading.Thread(target=_scheduler_loop, args=(bot,), daemon=True, name="VahtaScheduler")
    t.start()
    logger.info("[Scheduler] Планировщик запущен (интервал: %d ч.).", INTERVAL_HOURS)
