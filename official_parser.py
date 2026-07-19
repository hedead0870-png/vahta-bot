"""
official_parser.py — основа для загрузчиков официальных вакансий.

Структура:
  - BaseParser      — абстрактный базовый класс для всех загрузчиков
  - run_all_parsers — запускает все зарегистрированные загрузчики последовательно

Чтобы добавить новый источник:
  1. Создать класс, наследующий BaseParser.
  2. Реализовать метод fetch() — он должен возвращать список словарей
     с ключами: company_name, profession, city, salary, schedule,
                description, contact, source_url.
  3. Добавить экземпляр класса в список PARSERS ниже.

Пример:

    class MyCompanyParser(BaseParser):
        def fetch(self):
            # Загрузить страницу, распарсить, вернуть список вакансий
            return [
                {
                    "company_name": "ООО Пример",
                    "profession":   "Сварщик",
                    "city":         "Москва",
                    "salary":       "120 000",
                    "schedule":     "60/30",
                    "description":  "Описание вакансии",
                    "contact":      "+7 900 000-00-00",
                    "source_url":   "https://example.com/vacancies/1",
                }
            ]
"""

import logging
import database as db

logger = logging.getLogger(__name__)


def get_or_create_source_id(company_name: str, vacancies_url: str,
                             website: str | None = None) -> int:
    """Возвращает id источника по company_name, создаёт или обновляет запись.

    Логика делегирована в db.add_official_source(), которая делает upsert:
    - если компания найдена по company_name — обновляет vacancies_url и website;
    - если нет — создаёт новую запись.
    """
    return db.add_official_source(company_name, vacancies_url, website)


class BaseParser:
    """Абстрактный загрузчик вакансий с официального источника.

    Атрибуты, которые должен задать наследник:
      source_id (int) — id записи в таблице official_sources.
                        Используется для обновления last_update.
    """

    source_id: int | None = None

    def fetch(self) -> list[dict]:
        """Загружает вакансии и возвращает список словарей.
        Должен быть переопределён в наследнике.
        """
        raise NotImplementedError

    def run(self) -> dict:
        """Запускает загрузчик, сохраняет вакансии в БД.
        Возвращает словарь {'fetched': int, 'saved': int, 'duplicates': int}.
        """
        try:
            vacancies = self.fetch()
        except Exception as e:
            logger.error("[%s] Ошибка при загрузке: %s", self.__class__.__name__, e)
            return {"fetched": 0, "saved": 0, "duplicates": 0}

        saved = 0
        duplicates = 0
        new_vacancies: list[dict] = []
        for vac in vacancies:
            result = db.save_official_vacancy(vac)
            if result is not None:
                saved += 1
                new_vacancies.append(vac)
            else:
                duplicates += 1

        if self.source_id is not None:
            try:
                db.touch_source(self.source_id)
            except Exception as e:
                logger.warning("[%s] Не удалось обновить last_update: %s",
                               self.__class__.__name__, e)

        logger.info("[%s] Загружено: %d, сохранено: %d, дублей: %d",
                    self.__class__.__name__, len(vacancies), saved, duplicates)
        return {
            "fetched": len(vacancies),
            "saved": saved,
            "duplicates": duplicates,
            "new_vacancies": new_vacancies,
        }


# ── Реестр загрузчиков ────────────────────────────────────────
# Добавляйте экземпляры своих парсеров сюда:

PARSERS: list[BaseParser] = []


def discover_parsers() -> None:
    """Автоматически импортирует все модули из пакета parsers/.
    Каждый модуль при загрузке регистрирует свой класс в PARSERS.
    Повторный вызов безопасен — Python кэширует уже загруженные модули.
    """
    import importlib
    import pkgutil
    try:
        import parsers as _pkg
    except ImportError:
        logger.warning("Пакет parsers/ не найден — автоматическое обнаружение пропущено.")
        return
    for _, module_name, _ in pkgutil.iter_modules(_pkg.__path__):
        try:
            importlib.import_module(f"parsers.{module_name}")
            logger.debug("Парсер загружен: parsers.%s", module_name)
        except Exception as e:
            logger.error("Ошибка загрузки парсера parsers.%s: %s", module_name, e)


def run_all_parsers() -> list[dict]:
    """Запускает все зарегистрированные загрузчики последовательно.
    Возвращает список результатов по каждому парсеру.
    """
    results = []
    for parser in PARSERS:
        name = parser.__class__.__name__
        logger.info("Запуск парсера: %s", name)
        result = parser.run()
        result["parser"] = name
        results.append(result)
    return results
