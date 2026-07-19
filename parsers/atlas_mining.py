"""
parsers/atlas_mining.py — парсер вакансий Атлас Майнинг.

Источник: https://www.atlasmining.ru/career/
"""

import re
import logging
import requests
from bs4 import BeautifulSoup

from official_parser import BaseParser, PARSERS, get_or_create_source_id

logger = logging.getLogger(__name__)

COMPANY_NAME  = "Атлас Майнинг"
VACANCIES_URL = "https://www.atlasmining.ru/career/"
WEBSITE       = "https://www.atlasmining.ru/"
BASE_URL      = "https://www.atlasmining.ru"

_RE_SCHEDULE = re.compile(r'\b(\d{2,3}\s*/\s*\d{2,3})\b')
_RE_SALARY   = re.compile(
    r'(?:зарплата|оклад|з/п|заработная плата)[^\d]*([\d\s]+(?:000)?)\s*(?:руб|₽)',
    re.IGNORECASE,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _extract_schedule(text: str) -> str | None:
    m = _RE_SCHEDULE.search(text)
    return m.group(1).replace(" ", "") if m else None


def _extract_salary(text: str) -> str | None:
    m = _RE_SALARY.search(text)
    return m.group(1).strip() + " руб." if m else None


def _parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    vacancies = []
    for item in soup.select("details.spollers__item"):
        post_el = item.select_one(".post")
        profession = post_el.get_text(strip=True) if post_el else None
        if not profession:
            continue
        region_el  = item.select_one(".region")
        company_el = item.select_one(".company")
        city       = region_el.get_text(strip=True)  if region_el  else None
        enterprise = company_el.get_text(strip=True) if company_el else None

        btn  = item.select_one("a.button")
        href = btn["href"] if btn and btn.get("href") else ""
        if href.startswith("/"):
            source_url = BASE_URL + href.split("?")[0]
        else:
            source_url = href or VACANCIES_URL

        body_el     = item.select_one(".spollers__body .text")
        description = body_el.get_text("\n", strip=True) if body_el else None
        schedule    = _extract_schedule(description) if description else None
        salary      = _extract_salary(description)   if description else None

        vacancies.append({
            "company_name": COMPANY_NAME,
            "profession":   profession,
            "city":         city or enterprise or "Амурская обл.",
            "salary":       salary,
            "schedule":     schedule,
            "description":  description,
            "contact":      source_url,
            "source_url":   source_url,
        })
    return vacancies


class AtlasMiningParser(BaseParser):
    """Загрузчик вакансий с сайта Атлас Майнинг."""

    def __init__(self):
        self.source_id = get_or_create_source_id(COMPANY_NAME, VACANCIES_URL, WEBSITE)

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
            soup = BeautifulSoup(resp.text, "html.parser")
            next_link = soup.find("a", href=re.compile(rf"PAGEN_1={page + 1}"))
            if not next_link:
                break
            page += 1
        return all_vacancies


# Регистрируем в реестре
PARSERS.append(AtlasMiningParser())
