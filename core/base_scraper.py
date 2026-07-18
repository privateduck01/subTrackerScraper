import os
import aiohttp
from typing import List
from models.preset import PresetTier, Preset
from abc import ABC, abstractmethod

OUTPUT_ICONS_DIR = "icons"
# Базовый URL, откуда Android будет грузить картинки. Для offline-first используем локальные ассеты.
LOCAL_ASSET_BASE = "icons/"

class BaseScraper(ABC):
    """
    Абстрактный класс, от которого должны наследоваться все парсеры сервисов.
    """
    id: str
    name: str
    domain: str = ""      # Используется для API логотипов, если нет прямой ссылки
    icon_url: str = ""    # Прямая ссылка на иконку (приоритет над domain)
    icon_file: str = ""   # Ручная привязка локального файла (например "custom.png")
    default_tier: int = 0

    skeleton: dict = None

    @abstractmethod
    async def fetch_prices(self, session: aiohttp.ClientSession) -> List[PresetTier]:
        """
        Основной метод парсинга. Должен возвращать список тарифов.
        Параметр session нужен для переиспользования одного HTTP-подключения (ускоряет работу).
        """
        pass

    def _compress_and_save_image(self, content_or_path, base_dest_path: str, original_ext: str) -> str:
        """Сжимает изображение через Pillow и сохраняет в WebP."""
        if original_ext.lower() == 'svg':
            dest = f"{base_dest_path}.svg"
            if isinstance(content_or_path, str):
                import shutil
                shutil.copy2(content_or_path, dest)
            else:
                with open(dest, "wb") as f:
                    f.write(content_or_path)
            return "svg"

        try:
            from PIL import Image
            import io
            
            # Загружаем из файла или байтов
            if isinstance(content_or_path, str):
                img = Image.open(content_or_path)
            else:
                img = Image.open(io.BytesIO(content_or_path))
                
            with img:
                if img.mode not in ('RGBA', 'RGB'):
                    img = img.convert('RGBA')
                
                img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                
                dest = f"{base_dest_path}.webp"
                img.save(dest, "WEBP", quality=80)
                return "webp"
        except ImportError:
            dest = f"{base_dest_path}.{original_ext.strip('.')}"
            if isinstance(content_or_path, str):
                import shutil
                shutil.copy2(content_or_path, dest)
            else:
                with open(dest, "wb") as f:
                    f.write(content_or_path)
            return original_ext.strip('.')
        except Exception as e:
            print(f"[{self.id}] Ошибка сжатия: {e}")
            dest = f"{base_dest_path}.{original_ext.strip('.')}"
            if isinstance(content_or_path, str):
                import shutil
                shutil.copy2(content_or_path, dest)
            else:
                with open(dest, "wb") as f:
                    f.write(content_or_path)
            return original_ext.strip('.')

    async def _resolve_icon(self, session: aiohttp.ClientSession) -> str:
        """
        Скачивает иконку, если её нет, или использует существующую локальную.
        Возвращает путь к иконке для JSON (например "icons/spotify.webp").
        """
        os.makedirs(OUTPUT_ICONS_DIR, exist_ok=True)

        # 1. Если пользователь жестко задал файл вручную (manual override)
        if self.icon_file:
            # Копируем файл из templates/, если он там есть
            icon_source = os.path.join("templates", self.icon_file)
            if os.path.exists(icon_source):
                icon_ext = os.path.splitext(self.icon_file)[1].replace('.', '')
                base_dest = os.path.join(OUTPUT_ICONS_DIR, self.id)
                final_ext = self._compress_and_save_image(icon_source, base_dest, icon_ext)
                return f"{LOCAL_ASSET_BASE}{self.id}.{final_ext}"
            return f"{LOCAL_ASSET_BASE}{self.icon_file}"

        # 2. Если файл уже был скачан ранее (чтобы не качать каждый раз)
        for ext in ['webp', 'png', 'jpg', 'svg', 'jpeg']:
            possible_path = os.path.join(OUTPUT_ICONS_DIR, f"{self.id}.{ext}")
            if os.path.exists(possible_path):
                return f"{LOCAL_ASSET_BASE}{self.id}.{ext}"

        # 3. Скачиваем, если файла нет
        content = None
        final_ext = "png"

        # Сначала пробуем прямую ссылку, если она задана в скрапере
        if self.icon_url:
            try:
                async with session.get(self.icon_url) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get('content-type', 'image/png')
                        final_ext = 'svg' if 'svg' in content_type else 'jpg' if 'jpeg' in content_type else 'png'
                        content = await resp.read()
            except Exception as e:
                print(f"[{self.id}] Ошибка при скачивании по icon_url: {e}")

        # Если прямой ссылки нет (или она не сработала), пробуем API по домену
        if not content and self.domain:
            main_domain = self.domain.replace("www.", "").split('/')[0]
            
            # CompanyEnrich Logo API
            try:
                logo_url = f"https://api.companyenrich.com/logo/{main_domain}"
                async with session.get(logo_url) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get('content-type', 'image/png')
                        final_ext = 'svg' if 'svg' in content_type else 'jpg' if 'jpeg' in content_type else 'png'
                        content = await resp.read()
            except Exception:
                pass
            
            # Google Favicon API
            if not content:
                try:
                    favicon_url = f"https://www.google.com/s2/favicons?domain={main_domain}&sz=128"
                    async with session.get(favicon_url) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            final_ext = "png"
                except Exception:
                    pass

        # Сохраняем скачанный контент в файл с сжатием
        if content:
            base_dest = os.path.join(OUTPUT_ICONS_DIR, self.id)
            saved_ext = self._compress_and_save_image(content, base_dest, final_ext)
            return f"{LOCAL_ASSET_BASE}{self.id}.{saved_ext}"

        return "" # Если совсем ничего не нашли

    async def execute(self, session: aiohttp.ClientSession) -> Preset:
        """
        Умное слияние: берет каркас из JSON (если есть) и обновляет цены из fetch_prices.
        """
        # Сначала пытаемся получить свежие цены
        scraped_tiers = []
        try:
            scraped_tiers = await self.fetch_prices(session)
        except Exception as e:
            print(f"[{self.id}] Ошибка при парсинге цен: {e}")

        # Умное слияние с каркасом
        final_tiers = []
        tags = []
        if self.skeleton:
            self.name = self.skeleton.get("name", self.name)
            self.domain = self.skeleton.get("domain", self.domain)
            self.icon_url = self.skeleton.get("iconUrl", self.icon_url)
            self.icon_file = self.skeleton.get("icon_file", self.icon_file)
            self.default_tier = self.skeleton.get("defaultTier", self.default_tier)
            tags = self.skeleton.get("tags", [])

            scraped_tiers_dict = {t.name: t for t in scraped_tiers}

            for skel_tier in self.skeleton.get("tiers", []):
                tier_name = skel_tier.get("name", "")

                # Создаем Pydantic объект из словаря
                tier_obj = PresetTier(**skel_tier)

                # Если парсер нашел этот тариф на сайте, мёржим цены поштучно по региону:
                # регион, который скрапер реально вернул, обновляется; регионы, которые
                # скрапер не проверял (или не смог получить), остаются из каркаса, а не
                # пропадают. Раньше здесь было полное присваивание tier_obj.prices = ...,
                # из-за чего скрапер, вернувший цены только для part региона, стирал все
                # остальные регионы каркаса (см. историю бага с apple-music).
                if tier_name in scraped_tiers_dict:
                    scraped_by_region = {p.region: p for p in scraped_tiers_dict[tier_name].prices}
                    merged_prices = [
                        scraped_by_region.pop(price.region, price) for price in tier_obj.prices
                    ]
                    merged_prices.extend(scraped_by_region.values())
                    tier_obj.prices = merged_prices

                final_tiers.append(tier_obj)
        else:
            final_tiers = scraped_tiers
            
        # Скачиваем или находим иконку (теперь учитывается обновленный domain/icon_file)
        resolved_icon = await self._resolve_icon(session)
        
        return Preset(
            id=self.id,
            name=self.name,
            iconUrl=resolved_icon,
            tiers=final_tiers,
            defaultTier=self.default_tier,
            tags=tags
        )
