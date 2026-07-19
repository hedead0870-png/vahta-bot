"""
parsers/nordgold.py — парсер вакансий Нордголд (Nordgold).

Источник: https://www.nordgoldjobs.com/vacancy/
CMS: Bitrix. Официальный карьерный портал компании.

Особенности сайта:
- Детальные страницы вакансий (/vacancy/job-detail.php?ID=...) редиректят на
  главную страницу — это поведение самого сайта, не ошибка парсера.
- Листинг /vacancy/ содержит актуальные открытые позиции.
- Поле location в карточках не заполнено сайтом.
- Source_url указывает на официальный карьерный портал nordgoldjobs.com.
"""

import logging
import requests
from bs4 import BeautifulSoup

from official_parser import BaseParser, PARSERS, get_or_create_source_id

logger = logging.getLogger(__name__)

COMPANY_NAME  = "Нордголд"
VACANCIES_URL = "https://www.nordgoldjobs.com/vacancy/"
WEBSITE       = "https://www.nordgoldjobs.com/"
BASE_URL      = "https://www.nordgoldjobs.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def _parse_listing(html: str) -> list[dict]:
    """Парсит страницу листинга вакансий Нордголда."""
    soup = BeautifulSoup(html, "html.parser")
    vacancies = []

    for item in soup.select("a.vacancies_item"):
        href = item.get("href", "")
        if not href:
            continue
        source_url = (BASE_URL + href) if href.startswith("/") else href

        # Профессия
        title_el = item.select_one(".vacancies_title p")
        profession = title_el.get_text(strip=True) if title_el else None
        if not profession:
            continue

        # Город — пробуем data-атрибут кнопки «Откликнуться»
        city = None
        apply_btn = item.select_one("[data-location]")
        if apply_btn:
            loc = apply_btn.get("data-location", "").strip()
            city = loc if loc else None

        # Если в карточке нет — пробуем блок .vacancies_location
        if not city:
            loc_el = item.select_one(".vacancies_location p")
            if loc_el:
                loc = loc_el.get_text(strip=True)
                city = loc if loc else None

        vacancies.append({
            "company_name": COMPANY_NAME,
            "profession":   profession,
            "city":         city,
            "salary":       None,   # сайт не публикует зарплату в листинге
            "schedule":     None,   # детальные страницы не доступны (redirect)
            "description":  None,
            "contact":      source_url,
            "source_url":   source_url,
        })

    return vacancies


class NordgoldParser(BaseParser):
    """Загрузчик вакансий с карьерного портала Нордголд (nordgoldjobs.com).

    Парсит листинг /vacancy/ — все актуальные вакансии на одной странице.
    Детальные страницы недоступны (сайт делает redirect на главную), поэтому
    используем данные из карточек листинга.
    """

    def __init__(self):
        self.source_id = get_or_create_source_id(COMPANY_NAME, VACANCIES_URL, WEBSITE)

    def fetch(self) -> list[dict]:
        logger.info("[Nordgold] Загружаю листинг: %s", VACANCIES_URL)
        try:
            resp = requests.get(VACANCIES_URL, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("[Nordgold] Ошибка загрузки листинга: %s", e)
            return []

        vacancies = _parse_listing(resp.text)
        logger.info("[Nordgold] Найдено вакансий на странице: %d", len(vacancies))
        return vacancies


# Регистрируем в реестре
PARSERS.append(NordgoldParser())
