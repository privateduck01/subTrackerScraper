import aiohttp
import re
from typing import List
from core.base_scraper import BaseScraper
from models.preset import PresetTier, PresetPrice

class SkyScraper(BaseScraper):
    id = "sky"
    name = "Sky"
    icon_url = "https://upload.wikimedia.org/wikipedia/commons/1/13/Sky_logo_2020.svg"
    default_tier = 0

    async def fetch_prices(self, session: aiohttp.ClientSession) -> List[PresetTier]:
        url = "https://www.sky.com/shop"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        tiers_data = {
            "Sky Stream, TV & Netflix": [],
            "Sky Sports Bundle": [],
            "Sky Cinema Bundle": []
        }
        
        try:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # В UK цены обычно в фунтах (£)
                    matches = re.findall(r'£([0-9]{2})', html)
                    if matches:
                        prices = sorted([float(p) for p in set(matches)])
                        
                        if prices:
                            # Условная логика маппинга цен к популярным бандлам
                            base_tv = prices[0] if len(prices) > 0 else 28.0
                            sports = prices[len(prices)//2] if len(prices) > 2 else base_tv + 20
                            cinema = prices[1] if len(prices) > 1 else base_tv + 10
                            
                            tiers_data["Sky Stream, TV & Netflix"].append(
                                PresetPrice(cost=base_tv, currency="GBP", region="GB")
                            )
                            tiers_data["Sky Sports Bundle"].append(
                                PresetPrice(cost=sports, currency="GBP", region="GB")
                            )
                            tiers_data["Sky Cinema Bundle"].append(
                                PresetPrice(cost=cinema, currency="GBP", region="GB")
                            )
                else:
                    print(f"Failed to fetch Sky: {response.status}")
        except Exception as e:
            print(f"Error fetching Sky: {e}")

        result_tiers = []
        for name, prices in tiers_data.items():
            if prices:
                result_tiers.append(
                    PresetTier(name=name, prices=prices, periodQty=1, periodUnit="MONTH")
                )
                
        return result_tiers
