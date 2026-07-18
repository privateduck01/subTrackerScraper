import aiohttp
import re
from typing import List
from core.base_scraper import BaseScraper
from models.preset import PresetTier, PresetPrice

class DaznScraper(BaseScraper):
    id = "dazn"
    name = "DAZN"
    icon_url = "https://upload.wikimedia.org/wikipedia/commons/7/71/DAZN_logo.svg"
    default_tier = 0

    async def fetch_prices(self, session: aiohttp.ClientSession) -> List[PresetTier]:
        markets = {
            "en-DE": ("EUR", "DE"),
            "en-IT": ("EUR", "IT"),
            "en-GB": ("GBP", "GB")
        }
        
        tiers_data = {
            "Standard / Monthly": [],
            "Annual": []
        }
        
        for market, (currency, region) in markets.items():
            url = f"https://www.dazn.com/{market}/welcome"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            try:
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Парсим цены из HTML
                        # DAZN использует Next.js или React. Ищем символы валюты.
                        # В Германии DAZN стоит около 29.99 EUR - 44.99 EUR
                        
                        pattern = r'([0-9]{2}[.,][0-9]{2})'
                        matches = re.findall(pattern, html)
                        
                        if matches:
                            prices = sorted([float(p.replace(',', '.')) for p in set(matches) if 5.0 < float(p.replace(',', '.')) < 100.0])
                            if prices:
                                # Предполагаем, что самая большая цена за месяц без контракта
                                monthly_price = prices[-1] if prices else 29.99
                                annual_price = prices[0] * 12 if len(prices) > 1 else monthly_price * 10
                                
                                tiers_data["Standard / Monthly"].append(
                                    PresetPrice(cost=monthly_price, currency=currency, region=region)
                                )
                                tiers_data["Annual"].append(
                                    PresetPrice(cost=annual_price, currency=currency, region=region)
                                )
            except Exception as e:
                print(f"Error fetching DAZN {market}: {e}")

        result_tiers = []
        for name, prices in tiers_data.items():
            if prices:
                result_tiers.append(
                    PresetTier(name=name, prices=prices, periodQty=1, periodUnit="MONTH" if "Monthly" in name else "YEAR")
                )
                
        return result_tiers
