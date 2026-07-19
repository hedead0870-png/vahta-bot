"""
parsers/polyus.py — парсер вакансий ПАО «Полюс» (крупнейший золотодобытчик России).

Источник: https://polyus.com/ru/about/career/vacancies/
TODO: реализовать полноценный fetch() после изучения структуры страницы.
"""

import logging
import requests
from bs4 import BeautifulSoup

from official_parser import BaseParser, PARSERS, get_or_create_source_id

logger = logging.getLogger(__name__)

COMPANY_NAME  = "Полюс"
VACANCIES_URL = "https://polyus.com/ru/about/career/vacancies/"
WEBSITE       = "https://polyus.com/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


class PolyusParser(BaseParser):
    """Загрузчик вакансий с сайта Полюс.
    
    Для активации: реализуйте _parse_page() под фактическую HTML-структуру сайта
    и уберите ранний return из fetch().
    """

    def __init__(self):
        self.source_id = get_or_create_source_id(COMPANY_NAME, VACANCIES_URL, WEBSITE)

    def fetch(self) -> list[dict]:
        logger.info("[Polyus] fetch() — парсер в разработке, возвращаем пустой список.")
        # TODO: раскомментировать и реализовать после изучения структуры сайта
        # try:
        #     resp = requests.get(VACANCIES_URL, headers=HEADERS, timeout=15)
        #     resp.raise_for_status()
        #     return _parse_page(resp.text)
        # except Exception as e:
        #     logger.error("[Polyus] Ошибка: %s", e)
        return []


# Регистрируем в реестре
PARSERS.append(PolyusParser())
