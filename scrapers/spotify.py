import aiohttp
from typing import List
from core.base_scraper import BaseScraper
from models.preset import PresetTier, PresetPrice

class SpotifyScraper(BaseScraper):
    id = "spotify"
    name = "Spotify"
    icon_url = "https://upload.wikimedia.org/wikipedia/commons/1/19/Spotify_logo_without_text.svg"
    default_tier = 0

    async def fetch_prices(self, session: aiohttp.ClientSession) -> List[PresetTier]:
        # Список рынков, которые мы хотим спарсить
        markets = {
            "us": "USD",
            "gb": "GBP", 
            "de": "EUR" # Германия как представитель EU
        }

        tiers_data = {
            "Individual": [],
            "Duo": [],
            "Family": []
        }

        for market, currency in markets.items():
            url = f"https://www.spotify.com/{market}/premium/"
            try:
                # В реальных условиях Spotify может потребовать заголовки User-Agent
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        print(f"Failed to fetch Spotify {market}: {response.status}")
                        continue
                    
                    html = await response.text()
                    
                    # Парсинг HTML с помощью BeautifulSoup
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, "html.parser")
                    
                    import json
                    import re
                    
                    # Попытка 1: Ищем __NEXT_DATA__
                    script_tag = soup.find("script", id="__NEXT_DATA__")
                    parsed_successfully = False
                    
                    if script_tag:
                        try:
                            data = json.loads(script_tag.string)
                            offers = data['props']['pageProps']['initialState']['offers']['items']
                            plan_mapping = {
                                "premium_individual": "Individual",
                                "premium_duo": "Duo",
                                "premium_family": "Family"
                            }
                            for offer in offers.values():
                                plan_id = offer.get("plan", "")
                                if plan_id in plan_mapping:
                                    price_str = offer.get("price", {}).get("value", "0")
                                    match = re.search(r"([0-9]+[.,][0-9]+)", price_str)
                                    if match:
                                        clean_price = float(match.group(1).replace(",", "."))
                                        tier_name = plan_mapping[plan_id]
                                        tiers_data[tier_name].append(
                                            PresetPrice(cost=clean_price, currency=currency, region=market.upper())
                                        )
                            parsed_successfully = True
                        except Exception as e:
                            print(f"Failed to parse __NEXT_DATA__ for {market}: {e}")

                    # Попытка 2: Ищем цены с помощью регулярных выражений (если __NEXT_DATA__ нет или он изменился)
                    if not parsed_successfully:
                        # Ищем паттерны типа "premium_individual"... "value":"$11.99"
                        plan_mapping = {
                            "premium_individual": "Individual",
                            "premium_duo": "Duo",
                            "premium_family": "Family"
                        }
                        for raw_plan_id, tier_name in plan_mapping.items():
                            # Ищем в сыром HTML
                            pattern = rf'"{raw_plan_id}".{{0,200}}?"price".{{0,50}}?"value":"[^0-9]*([0-9]+[.,][0-9]+)[^"]*"'
                            matches = re.findall(pattern, html)
                            if matches:
                                clean_price = float(matches[0].replace(",", "."))
                                tiers_data[tier_name].append(
                                    PresetPrice(cost=clean_price, currency=currency, region=market.upper())
                                )
                                parsed_successfully = True
                                
                    if not parsed_successfully:
                        print(f"Could not extract prices for Spotify {market}. The page structure might have changed or access was blocked.")
                        
            except Exception as e:
                print(f"Error fetching Spotify {market}: {e}")

        # Собираем итоговый список
        result_tiers = []
        for name, prices in tiers_data.items():
            if prices: # Добавляем тариф, только если удалось собрать цены
                result_tiers.append(
                    PresetTier(
                        name=name,
                        prices=prices,
                        periodQty=1,
                        periodUnit="MONTH"
                    )
                )
                
        return result_tiers
