import aiohttp
import json
import re
from typing import List
from core.base_scraper import BaseScraper
from models.preset import PresetTier, PresetPrice

class NetflixScraper(BaseScraper):
    id = "netflix"
    name = "Netflix"
    icon_url = "https://upload.wikimedia.org/wikipedia/commons/0/08/Netflix_2015_logo.svg"
    default_tier = 0

    async def fetch_prices(self, session: aiohttp.ClientSession) -> List[PresetTier]:
        markets = {
            "us": "USD",
            "gb": "GBP",
            "de": "EUR"
        }

        tiers_data = {
            "Basic / Standard with ads": [],
            "Standard": [],
            "Premium": []
        }

        for market, currency in markets.items():
            # URL для signup часто содержит актуальные цены без авторизации
            url = f"https://www.netflix.com/{market}/signup/planform"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9"
            }
            try:
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status != 200:
                        print(f"Failed to fetch Netflix {market}: {response.status}")
                        continue
                    
                    html = await response.text()
                    
                    # Netflix обычно хранит стейт в объекте window.netflix
                    # Попробуем извлечь цены через Regex, так как парсить весь гигантский JS контекст тяжело
                    # Паттерн ищет названия планов и цены рядом
                    
                    tier_mapping = {
                        "Basic": "Basic / Standard with ads",
                        "Standard with ads": "Basic / Standard with ads",
                        "Standard": "Standard",
                        "Premium": "Premium"
                    }
                    
                    parsed_any = False
                    # Ищем куски вроде "tierName":"Standard","price":15.49 или "planPrice":"15.49"
                    # Более надежный способ для Netflix:
                    for raw_tier, mapped_tier in tier_mapping.items():
                        # Ищем совпадения цен для определенного тарифа
                        pattern = rf'"{raw_tier}".{{0,300}}?"price"\s*:\s*"?([0-9]+[.,][0-9]+)'
                        matches = re.findall(pattern, html, re.IGNORECASE)
                        if matches:
                            clean_price = float(matches[0].replace(",", "."))
                            tiers_data[mapped_tier].append(
                                PresetPrice(cost=clean_price, currency=currency, region=market.upper())
                            )
                            parsed_any = True
                    
                    if not parsed_any:
                        print(f"Could not extract prices for Netflix {market}. Bot protection or structure change.")

            except Exception as e:
                print(f"Error fetching Netflix {market}: {e}")

        result_tiers = []
        for name, prices in tiers_data.items():
            if prices:
                # Оставляем только уникальные регионы (защита от дублей)
                unique_prices = {p.region: p for p in prices}.values()
                result_tiers.append(
                    PresetTier(
                        name=name,
                        prices=list(unique_prices),
                        periodQty=1,
                        periodUnit="MONTH"
                    )
                )
                
        return result_tiers
