"""
parsers/polyus.py — парсер вакансий ПАО «Полюс» (крупнейший золотодобытчик России).

Источник: https://career.polyus.com/vacancies/
CMS: Bitrix, server-side rendering.
Пагинация: ?PAGEN_1=N (10 вакансий на страницу, ~19 страниц).

Все нужные поля (профессия, город, график, описание, ссылка) доступны прямо
на листинге — детальные страницы не запрашиваются.
Зарплата на сайте не публикуется — поле salary остаётся None.
"""

import logging
import requests
from bs4 import BeautifulSoup

from official_parser import BaseParser, PARSERS, get_or_create_source_id

logger = logging.getLogger(__name__)

COMPANY_NAME  = "Полюс"
VACANCIES_URL = "https://career.polyus.com/vacancies/"
WEBSITE       = "https://career.polyus.com/"
BASE_URL      = "https://career.polyus.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def _parse_page(html: str) -> list[dict]:
    """Парсит одну страницу листинга и возвращает список словарей вакансий."""
    soup = BeautifulSoup(html, "html.parser")
    vacancies = []

    for item in soup.select("div.block-vacancies__item"):
        link_el = item.select_one("a.card-result")
        if not link_el:
            continue

        href = link_el.get("href", "")
        # Пропускаем корневую ссылку на листинг
        if not href or href in ("/vacancies/", "/vacancies-students/"):
            continue
        source_url = BASE_URL + href if href.startswith("/") else href

        # Профессия
        title_el = link_el.select_one("h3.card-result__title")
        profession = title_el.get_text(strip=True) if title_el else None
        if not profession:
            continue

        # Описание — список обязанностей из карточки листинга
        desc_items = link_el.select(
            "li.card-result__list-item div.card-result__list-text"
        )
        description = (
            "\n".join(el.get_text(strip=True) for el in desc_items) or None
        )

        # Мета-поля: Сфера, Тип занятости, Предприятие, График работы
        meta: dict[str, str] = {}
        for di in link_el.select("div.card-result__description-item"):
            label_el = di.select_one(".card-result__description-title")
            value_el = di.select_one(".card-result__description-text")
            if label_el and value_el:
                key = label_el.get_text(strip=True).rstrip(":")
                meta[key] = value_el.get_text(strip=True)

        schedule   = meta.get("График работы")
        enterprise = meta.get("Предприятие")

        # Город
        loc_el = link_el.select_one("div.card-result__location")
        city = loc_el.get_text(strip=True) if loc_el else None
        if not city:
            city = enterprise  # fallback: название предприятия

        vacancies.append({
            "company_name": COMPANY_NAME,
            "profession":   profession,
            "city":         city,
            "salary":       None,       # сайт не публикует конкретные суммы
            "schedule":     schedule,
            "description":  description,
            "contact":      source_url,
            "source_url":   source_url,
        })

    return vacancies


class PolyusParser(BaseParser):
    """Загрузчик вакансий с карьерного портала Полюс (career.polyus.com).

    Обходит страницы листинга (?PAGEN_1=N) и извлекает все поля прямо из карточек.
    Дублирование исключено через UNIQUE(company_name, profession, city, source_url) в БД.
    """

    def __init__(self):
        self.source_id = get_or_create_source_id(COMPANY_NAME, VACANCIES_URL, WEBSITE)

    def fetch(self) -> list[dict]:
        all_vacancies: list[dict] = []
        page = 1

        while True:
            url = VACANCIES_URL if page == 1 else f"{VACANCIES_URL}?PAGEN_1={page}"
            logger.info("[Polyus] Загружаю страницу %d: %s", page, url)
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.error("[Polyus] Ошибка загрузки страницы %d: %s", page, e)
                break

            found = _parse_page(resp.text)
            if not found:
                logger.info("[Polyus] Страница %d пуста — остановка.", page)
                break

            logger.info("[Polyus] Страница %d: найдено %d вакансий.", page, len(found))
            all_vacancies.extend(found)

            # Проверяем наличие следующей страницы через стрелку пагинатора.
            # Bitrix может добавлять ysclid и другие параметры к href,
            # поэтому ищем тег <a> (не <button>) со классом paginator__arrow--next.
            soup = BeautifulSoup(resp.text, "html.parser")
            next_arrow = soup.select_one("a.paginator__arrow--next")
            if not next_arrow:
                logger.info("[Polyus] Страница %d — последняя.", page)
                break

            page += 1

        return all_vacancies


# Регистрируем в реестре
PARSERS.append(PolyusParser())
