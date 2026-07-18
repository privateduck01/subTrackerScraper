import os
import json
import shutil
import asyncio
import aiohttp
import re

# Пути к старому проекту
OLD_PROJECT_ICONS_DIR = "/Users/bulbadyshka/Documents/programming/personal_projects/sub-tracker/src/assets/icons"
OLD_PROJECT_LOGOS_DIR = "/Users/bulbadyshka/Documents/programming/personal_projects/sub-tracker/public/icons"
SERVICES_JSON_PATH = "/Users/bulbadyshka/Documents/programming/personal_projects/sub-tracker/src/assets/services.json"

# Куда сохранять в новом проекте
OUTPUT_ICONS_DIR = "output/icons"

async def process_service(session, service):
    domain = service.get("domain", "")
    name = service.get("name", "")
    if not domain:
        return

    # Логика формирования имени из старого скрипта download-icons.mjs
    safe_domain_name = re.sub(r'^www\.', '', domain, flags=re.IGNORECASE)
    safe_domain_name = re.sub(r'[^a-z0-9]', '_', safe_domain_name, flags=re.IGNORECASE).lower()
    
    # Логика формирования имени из старого скрипта download-logos.js
    safe_logo_name = re.sub(r'[^a-z0-9]', '_', name, flags=re.IGNORECASE).lower()

    # Пути куда будем сохранять
    target_path_png = os.path.join(OUTPUT_ICONS_DIR, f"{safe_domain_name}.png")
    
    # --- ШАГ 1: ПЕРЕНОС СУЩЕСТВУЮЩИХ ИКОНОК ---
    # Пробуем найти и скопировать из старого проекта
    possible_icon = os.path.join(OLD_PROJECT_ICONS_DIR, f"{safe_domain_name}.png")
    if os.path.exists(possible_icon) and not os.path.exists(target_path_png):
        shutil.copy2(possible_icon, target_path_png)
        print(f"📦 Перенесено из старого проекта: {safe_domain_name}.png")
        return
        
    # Пробуем найти логотип
    for ext in ['png', 'jpg', 'svg']:
        possible_logo = os.path.join(OLD_PROJECT_LOGOS_DIR, f"{safe_logo_name}.{ext}")
        target_logo_path = os.path.join(OUTPUT_ICONS_DIR, f"{safe_logo_name}.{ext}")
        if os.path.exists(possible_logo) and not os.path.exists(target_logo_path):
            shutil.copy2(possible_logo, target_logo_path)
            print(f"📦 Перенесено лого из старого проекта: {safe_logo_name}.{ext}")
            return

    if os.path.exists(target_path_png):
        return # Уже есть

    # --- ШАГ 2: ЛОГИКА ВЫГРУЗКИ ЧЕРЕЗ API ---
    # Если иконки нет, скачиваем её
    main_domain = domain.split('/')[0]
    
    # 2a. Пробуем скачать логотип через CompanyEnrich Logo API
    try:
        logo_url = f"https://api.companyenrich.com/logo/{main_domain}"
        async with session.get(logo_url) as resp:
            if resp.status == 200:
                content_type = resp.headers.get('content-type', 'image/png')
                ext = 'svg' if 'svg' in content_type else 'jpg' if 'jpeg' in content_type else 'png'
                content = await resp.read()
                
                target_logo_path = os.path.join(OUTPUT_ICONS_DIR, f"{safe_logo_name}.{ext}")
                with open(target_logo_path, "wb") as f:
                    f.write(content)
                print(f"✅ Скачано лого через API: {safe_logo_name}.{ext}")
                return
    except Exception as e:
        pass
        
    # 2b. Fallback на Google Favicons
    try:
        icon_url = f"https://www.google.com/s2/favicons?domain={main_domain}&sz=128"
        async with session.get(icon_url) as resp:
            if resp.status == 200:
                content = await resp.read()
                with open(target_path_png, "wb") as f:
                    f.write(content)
                print(f"✅ Скачана иконка через Google API: {safe_domain_name}.png")
    except Exception as e:
        print(f"❌ Ошибка загрузки для {name}: {e}")

async def main():
    print("Начинаем перенос иконок и загрузку недостающих...")
    os.makedirs(OUTPUT_ICONS_DIR, exist_ok=True)
    
    if not os.path.exists(SERVICES_JSON_PATH):
        print(f"Файл {SERVICES_JSON_PATH} не найден. Убедитесь, что старый проект на месте.")
        return
        
    with open(SERVICES_JSON_PATH, "r", encoding="utf-8") as f:
        services = json.load(f)
        
    async with aiohttp.ClientSession() as session:
        # Ограничиваем количество одновременных запросов, чтобы не забанили
        semaphore = asyncio.Semaphore(10)
        
        async def sem_task(service):
            async with semaphore:
                await process_service(session, service)
                
        tasks = [sem_task(s) for s in services]
        await asyncio.gather(*tasks)
        
    print("🎉 Все иконки успешно обработаны (перенесены или скачаны)!")

if __name__ == "__main__":
    # Фикс для Windows (на всякий случай)
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
