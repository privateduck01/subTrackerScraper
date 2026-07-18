import aiohttp
from typing import List
from .base_scraper import BaseScraper
from models.preset import PresetTier

class StaticScraper(BaseScraper):
    """
    Легковесный парсер для подписок, у которых есть только JSON-шаблон, 
    но нет своего Python-кода (scrapers/*.py). 
    Он ничего не парсит, вся магия происходит в BaseScraper.execute().
    """
    def __init__(self, skeleton: dict):
        self.skeleton = skeleton
        self.id = skeleton.get("id", "unknown")
        self.name = skeleton.get("name", "Unknown")
        self.domain = skeleton.get("domain", "")
        self.icon_url = skeleton.get("iconUrl", "")
        self.icon_file = skeleton.get("icon_file", "")
        self.default_tier = skeleton.get("defaultTier", 0)

    async def fetch_prices(self, session: aiohttp.ClientSession) -> List[PresetTier]:
        # Возвращаем пустой список. 
        # BaseScraper.execute увидит, что спарсенных цен нет, 
        # и просто оставит те цены, которые были указаны в JSON-каркасе.
        return []
