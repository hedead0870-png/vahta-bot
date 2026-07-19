"""
atlas_mining_parser.py — парсер вакансий Атлас Майнинг.

Источник: https://www.atlasmining.ru/career/
Наследуется от BaseParser (official_parser.py).
"""

import re
import logging
import requests
from bs4 import BeautifulSoup

import database as db
from official_parser import BaseParser, PARSERS

logger = logging.getLogger(__name__)

COMPANY_NAME  = "Атлас Майнинг"
BASE_URL      = "https://www.atlasmining.ru"
VACANCIES_URL = "https://www.atlasmining.ru/career/"
WEBSITE       = "https://www.atlasmining.ru/"

# Шаблоны для извлечения данных из текста описания
_RE_SCHEDULE = re.compile(
    r'\b(\d{2,3}\s*/\s*\d{2,3})\b'          # 30/30, 60/30, 45/45 …
)
_RE_SALARY = re.compile(
    r'(?:зарплата|оклад|з/п|заработная плата)[^\d]*'
    r'([\d\s]+(?:000)?)\s*(?:руб|₽)',
    re.IGNORECASE,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _get_or_create_source_id() -> int:
    """Возвращает id источника из БД, создаёт запись если её нет."""
    sources = db.get_active_sources()
    for s in sources:
        if s["vacancies_url"] == VACANCIES_URL:
            return s["id"]
    return db.add_official_source(
        company_name=COMPANY_NAME,
        vacancies_url=VACANCIES_URL,
        website=WEBSITE,
    )


def _extract_schedule(text: str) -> str | None:
    """Ищет паттерн вахтового графика (30/30, 60/30 …) в тексте."""
    m = _RE_SCHEDULE.search(text)
    return m.group(1).replace(" ", "") if m else None


def _extract_salary(text: str) -> str | None:
    """Пытается извлечь зарплату из текста описания."""
    m = _RE_SALARY.search(text)
    return m.group(1).strip() + " руб." if m else None


def _parse_page(html: str) -> list[dict]:
    """Парсит одну страницу и возвращает список вакансий."""
    soup = BeautifulSoup(html, "html.parser")
    vacancies = []

    for item in soup.select("details.spollers__item"):
        # Название вакансии
        post_el = item.select_one(".post")
        profession = post_el.get_text(strip=True) if post_el else None
        if not profession:
            continue

        # Регион и предприятие
        region_el  = item.select_one(".region")
        company_el = item.select_one(".company")
        city        = region_el.get_text(strip=True)  if region_el  else None
        enterprise  = company_el.get_text(strip=True) if company_el else None

        # Ссылка на вакансию
        btn = item.select_one("a.button")
        href = btn["href"] if btn and btn.get("href") else ""
        if href.startswith("/"):
            source_url = BASE_URL + href.split("?")[0]  # убираем back_url
        else:
            source_url = href or VACANCIES_URL

        # Описание
        body_el = item.select_one(".spollers__body .text")
        description = body_el.get_text("\n", strip=True) if body_el else None

        # Извлекаем поля из описания
        schedule = _extract_schedule(description) if description else None
        salary   = _extract_salary(description)   if description else None

        # Контакт — ссылка на страницу вакансии
        contact = source_url

        vacancies.append({
            "company_name": COMPANY_NAME,
            "profession":   profession,
            "city":         city or enterprise or "Амурская обл.",
            "salary":       salary,
            "schedule":     schedule,
            "description":  description,
            "contact":      contact,
            "source_url":   source_url,
        })

    return vacancies


class AtlasMiningParser(BaseParser):
    """Загрузчик вакансий с сайта Атлас Майнинг."""

    def __init__(self):
        self.source_id = _get_or_create_source_id()

    def fetch(self) -> list[dict]:
        all_vacancies: list[dict] = []
        page = 1

        while True:
            url = VACANCIES_URL if page == 1 else f"{VACANCIES_URL}?PAGEN_1={page}"
            logger.info("[AtlasMining] Загружаю страницу %d: %s", page, url)

            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.error("[AtlasMining] Ошибка загрузки страницы %d: %s", page, e)
                break

            found = _parse_page(resp.text)
            if not found:
                logger.info("[AtlasMining] Страница %d пуста — остановка.", page)
                break

            logger.info("[AtlasMining] Страница %d: найдено %d вакансий.", page, len(found))
            all_vacancies.extend(found)

            # Проверяем есть ли ссылка на следующую страницу
            soup = BeautifulSoup(resp.text, "html.parser")
            next_link = soup.find("a", href=re.compile(rf"PAGEN_1={page + 1}"))
            if not next_link:
                break
            page += 1

        return all_vacancies


# Регистрируем в реестре
PARSERS.append(AtlasMiningParser())
