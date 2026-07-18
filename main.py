import asyncio
import aiohttp
import importlib
import inspect
import json
import os
import shutil
import pkgutil
from typing import List

from core.base_scraper import BaseScraper
from core.validation import load_previous_presets, sanitize_presets
from models.preset import Preset

async def load_scrapers() -> List[BaseScraper]:
    """Автоматически находит и загружает все парсеры из папки scrapers/"""
    scrapers = []
    
    # Динамический импорт всех модулей из папки scrapers
    package = importlib.import_module("scrapers")
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"scrapers.{module_name}")
        
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, BaseScraper) and obj is not BaseScraper:
                scrapers.append(obj())
                
    return scrapers

def load_skeletons() -> dict:
    """Загружает JSON-каркасы из папки templates/"""
    skeletons = {}
    templates_dir = "templates"

    if not os.path.exists(templates_dir):
        return skeletons

    for filename in os.listdir(templates_dir):
        if filename.endswith(".json") and filename != "template.json":
            file_path = os.path.join(templates_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    skel_id = data.get("id")
                    if skel_id:
                        skeletons[skel_id] = data
            except Exception as e:
                print(f"[ERROR] Failed to load skeleton {filename}: {e}")
                
    return skeletons

async def main():
    skeletons = load_skeletons()
    scrapers = await load_scrapers()
    
    # 1. Привязываем каркасы к динамическим парсерам
    for scraper in scrapers:
        if scraper.id in skeletons:
            scraper.skeleton = skeletons[scraper.id]
            del skeletons[scraper.id] # Удаляем, чтобы не обрабатывать дважды
            print(f"[*] Hybrid mode active for {scraper.id}")
            
    # 2. Для оставшихся каркасов создаем чисто статические парсеры
    from core.static_scraper import StaticScraper
    for skel_id, skeleton in skeletons.items():
        scrapers.append(StaticScraper(skeleton))
        print(f"[*] Static mode active for {skel_id}")

    print(f"Total scrapers to run: {len(scrapers)}")
    
    presets = []
    
    # Используем одну HTTP сессию для всех парсеров
    async with aiohttp.ClientSession() as session:
        # Запускаем все парсеры параллельно (магия asyncio!)
        tasks = [scraper.execute(session) for scraper in scrapers]
        
        # return_exceptions=True позволяет коду продолжить работу, если один парсер упадет
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for scraper, result in zip(scrapers, results):
            if isinstance(result, Exception):
                print(f"[ERROR] Scraper {scraper.id} failed: {result}")
            elif isinstance(result, Preset):
                print(f"[SUCCESS] Scraper {scraper.id} completed successfully.")
                if hasattr(result, "model_dump"):
                    presets.append(result.model_dump())
                else:
                    presets.append(result.dict())
                
    # Санити-проверки перед записью: отбрасываем невалидные цены/валюты и
    # откатываем подозрительные скачки (>±60%) к предыдущему значению, чтобы
    # один сломанный селектор не разъехался по всем устройствам.
    # Пишем в корень репозитория (не в output/): raw.githubusercontent.com
    # раздаёт presets.json и icons/ приложению по корневому пути (см.
    # SyncWorker.kt), а сам скраппер публикуется в тот же репозиторий.
    output_dir = "."
    presets_path = f"{output_dir}/presets.json"

    previous_presets = load_previous_presets(presets_path)
    presets = sanitize_presets(presets, previous_presets)

    with open(presets_path, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)

    print("Done! presets.json generated.")

if __name__ == "__main__":
    # Если на Windows, иногда нужен этот фикс для asyncio
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
