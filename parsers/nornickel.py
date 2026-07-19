"""
parsers/nornickel.py — парсер вакансий ПАО «ГМК Норильский никель».

Источник: https://www.nornickel.ru/careers/vacancies/
TODO: реализовать полноценный fetch() после изучения структуры страницы.
"""

import logging
import requests

from official_parser import BaseParser, PARSERS, get_or_create_source_id

logger = logging.getLogger(__name__)

COMPANY_NAME  = "Норникель"
VACANCIES_URL = "https://www.nornickel.ru/careers/vacancies/"
WEBSITE       = "https://www.nornickel.ru/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


class NornickelParser(BaseParser):
    """Загрузчик вакансий с сайта Норникель.

    Для активации: реализуйте _parse_page() под фактическую HTML-структуру сайта
    и уберите ранний return из fetch().
    """

    def __init__(self):
        self.source_id = get_or_create_source_id(COMPANY_NAME, VACANCIES_URL, WEBSITE)

    def fetch(self) -> list[dict]:
        logger.info("[Nornickel] fetch() — парсер в разработке, возвращаем пустой список.")
        # TODO: реализовать после изучения структуры сайта
        return []


# Регистрируем в реестре
PARSERS.append(NornickelParser())
