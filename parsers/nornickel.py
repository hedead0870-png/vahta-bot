"""
parsers/nornickel.py — парсер вакансий ПАО «ГМК Норильский никель».

Источник: https://career.nornickel.ru/vacancies/
API:      POST https://career.nornickel.ru/api/vacancies/get/
          Тело: {"page": N} → JSON с полями items[], pagination, fullCount.
          Возвращает 40 вакансий на страницу (~19 страниц, ~744 вакансии).

Все нужные поля возвращаются напрямую из API — детальные страницы не нужны.
"""

import re
import logging
import requests

from official_parser import BaseParser, PARSERS, get_or_create_source_id

logger = logging.getLogger(__name__)

COMPANY_NAME  = "Норникель"
VACANCIES_URL = "https://career.nornickel.ru/vacancies/"
API_URL       = "https://career.nornickel.ru/api/vacancies/get/"
WEBSITE       = "https://career.nornickel.ru/"
BASE_URL      = "https://career.nornickel.ru"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language":  "ru-RU,ru;q=0.9",
    "Accept":           "application/json, text/javascript, */*",
    "Content-Type":     "application/json",
    "Referer":          "https://career.nornickel.ru/vacancies/",
}

_RE_NBSP = re.compile(r"&nbsp;|\xa0")


def _clean(text: str) -> str:
    """Убирает неразрывные пробелы и лишние пробелы."""
    return _RE_NBSP.sub(" ", text).strip()


def _extract_city(location: str) -> str | None:
    """Берёт первый фрагмент до запятой как название города."""
    location = _clean(location)
    if not location:
        return None
    return location.split(",")[0].strip() or None


def _build_salary(item: dict) -> str | None:
    """Собирает строку зарплаты из полей API."""
    salary_from = _clean(item.get("salaryFrom", ""))
    tax_status  = _clean(item.get("salaryTaxStatus", ""))
    if not salary_from:
        return None
    salary = f"от {salary_from} ₽"
    if tax_status:
        salary += f", {tax_status}"
    return salary


def _build_description(item: dict) -> str | None:
    """Формирует краткое описание из доступных полей карточки."""
    parts = []
    if item.get("jobEmployment"):
        parts.append(f"Занятость: {_clean(item['jobEmployment'])}")
    if item.get("experience"):
        parts.append(f"Опыт: {_clean(item['experience'])}")
    return ". ".join(parts) if parts else None


class NornickelParser(BaseParser):
    """Загрузчик вакансий с карьерного портала Норникеля (career.nornickel.ru).

    Использует JSON API (POST /api/vacancies/get/) с постраничной загрузкой.
    Пагинация определяется по наличию поля pagination.forward в ответе.
    Дублирование исключено через save_official_vacancy() в database.py.
    """

    def __init__(self):
        self.source_id = get_or_create_source_id(COMPANY_NAME, VACANCIES_URL, WEBSITE)

    def fetch(self) -> list[dict]:
        all_vacancies: list[dict] = []
        page = 1

        while True:
            logger.info("[Nornickel] Запрашиваю страницу %d...", page)
            try:
                resp = requests.post(
                    API_URL, headers=HEADERS, json={"page": page}, timeout=20
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("[Nornickel] Ошибка на странице %d: %s", page, e)
                break

            items = data.get("items", [])
            if not items:
                logger.info("[Nornickel] Страница %d пуста — остановка.", page)
                break

            logger.info("[Nornickel] Страница %d: %d вакансий.", page, len(items))

            for item in items:
                url = item.get("url", "")
                source_url = (BASE_URL + url) if url.startswith("/") else url
                if not source_url:
                    continue

                profession = _clean(item.get("title", ""))
                if not profession:
                    continue

                city        = _extract_city(item.get("location", ""))
                salary      = _build_salary(item)
                schedule    = _clean(item.get("timetable", "")) or None
                description = _build_description(item)

                all_vacancies.append({
                    "company_name": COMPANY_NAME,
                    "profession":   profession,
                    "city":         city,
                    "salary":       salary,
                    "schedule":     schedule,
                    "description":  description,
                    "contact":      source_url,
                    "source_url":   source_url,
                })

            # Проверяем наличие следующей страницы
            pagination = data.get("pagination") or {}
            if not pagination.get("forward"):
                logger.info("[Nornickel] Страница %d — последняя.", page)
                break

            page += 1

        return all_vacancies


# Регистрируем в реестре
PARSERS.append(NornickelParser())
