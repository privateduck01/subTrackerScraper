import json
import os
import re
from typing import Dict, List, Optional

# Активные коды ISO 4217. Используются как страховка от опечаток/мусора
# в валюте (например, скрапер вернул "0" или обрезанную строку).
ISO_4217_CODES = {
    "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AUD", "AWG", "AZN",
    "BAM", "BBD", "BDT", "BGN", "BHD", "BIF", "BMD", "BND", "BOB", "BRL",
    "BSD", "BTN", "BWP", "BYN", "BZD", "CAD", "CDF", "CHF", "CLP", "CNY",
    "COP", "CRC", "CUP", "CVE", "CZK", "DJF", "DKK", "DOP", "DZD", "EGP",
    "ERN", "ETB", "EUR", "FJD", "FKP", "GBP", "GEL", "GHS", "GIP", "GMD",
    "GNF", "GTQ", "GYD", "HKD", "HNL", "HRK", "HTG", "HUF", "IDR", "ILS",
    "INR", "IQD", "IRR", "ISK", "JMD", "JOD", "JPY", "KES", "KGS", "KHR",
    "KMF", "KPW", "KRW", "KWD", "KYD", "KZT", "LAK", "LBP", "LKR", "LRD",
    "LSL", "LYD", "MAD", "MDL", "MGA", "MKD", "MMK", "MNT", "MOP", "MRU",
    "MUR", "MVR", "MWK", "MXN", "MYR", "MZN", "NAD", "NGN", "NIO", "NOK",
    "NPR", "NZD", "OMR", "PAB", "PEN", "PGK", "PHP", "PKR", "PLN", "PYG",
    "QAR", "RON", "RSD", "RUB", "RWF", "SAR", "SBD", "SCR", "SDG", "SEK",
    "SGD", "SHP", "SLE", "SOS", "SRD", "SSP", "STN", "SYP", "SZL", "THB",
    "TJS", "TMT", "TND", "TOP", "TRY", "TTD", "TVD", "TWD", "TZS", "UAH",
    "UGX", "USD", "UYU", "UZS", "VES", "VND", "VUV", "WST", "XAF", "XCD",
    "XOF", "XPF", "YER", "ZAR", "ZMW", "ZWL",
}

MAX_CHANGE_RATIO = 0.6  # ±60%, см. docs/price_scraper_design.md


def load_previous_presets(path: str) -> Dict[str, dict]:
    """Загружает предыдущий presets.json (если есть) для diff-сравнения."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {p["id"]: p for p in data if "id" in p}
    except Exception as e:
        print(f"[VALIDATE] Не удалось прочитать предыдущий presets.json: {e}")
        return {}


def _price_lookup(preset: Optional[dict]) -> Dict[tuple, dict]:
    """(имя тира, регион) -> запись цены, для быстрого поиска предыдущего значения."""
    lookup = {}
    if not preset:
        return lookup
    for tier in preset.get("tiers", []):
        for price in tier.get("prices", []):
            lookup[(tier.get("name"), price.get("region"))] = price
    return lookup


def sanitize_presets(presets: List[dict], previous: Dict[str, dict]) -> List[dict]:
    """
    Прогоняет каждую цену через sanity-проверки перед записью в presets.json:
    - cost должен быть положительным числом;
    - currency должна быть валидным ISO 4217 кодом;
    - изменение цены относительно предыдущего прогона не должно превышать
      ±60% (иначе это, скорее всего, сломанный селектор, а не реальное
      подорожание) - такая запись откатывается к предыдущему значению.

    Если у пресета не осталось ни одного валидного тира, а предыдущая
    версия пресета есть - используется она целиком, чтобы одна пробитая
    страница не убила пресет из каталога.
    """
    sanitized = []

    for preset in presets:
        pid = preset.get("id", "?")
        prev_preset = previous.get(pid)
        prev_lookup = _price_lookup(prev_preset)

        clean_tiers = []
        for tier in preset.get("tiers", []):
            tier_name = tier.get("name")
            clean_prices = []

            for price in tier.get("prices", []):
                cost = price.get("cost")
                currency = str(price.get("currency") or "").upper()
                region = price.get("region", "")

                # cost == 0 - осознанный маркер "нет единой цены" (мобильная связь,
                # интернет-провайдеры и т.п., см. target_subscriptions.md - эта
                # категория вне области действия скраппера, пользователь вводит
                # сумму сам). Ошибка - только отрицательное или нечисловое значение.
                if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0:
                    print(f"[VALIDATE] {pid}/{tier_name}/{region}: некорректная цена {cost!r} — запись отброшена")
                    continue

                if not re.fullmatch(r"[A-Z]{3}", currency) or currency not in ISO_4217_CODES:
                    print(f"[VALIDATE] {pid}/{tier_name}/{region}: неизвестная валюта {currency!r} — запись отброшена")
                    continue

                prev_price = prev_lookup.get((tier_name, region))
                if prev_price and prev_price.get("currency") == currency:
                    old_cost = prev_price.get("cost", 0)
                    if isinstance(old_cost, (int, float)) and old_cost > 0:
                        ratio = abs(cost - old_cost) / old_cost
                        if ratio > MAX_CHANGE_RATIO:
                            print(
                                f"[VALIDATE] {pid}/{tier_name}/{region}: цена изменилась больше чем на "
                                f"{MAX_CHANGE_RATIO * 100:.0f}% ({old_cost} -> {cost}), похоже на сломанный "
                                f"парсер — оставляем предыдущее значение (needs_review)"
                            )
                            price = dict(price)
                            price["cost"] = old_cost
                            price["currency"] = prev_price.get("currency")

                clean_prices.append(price)

            if clean_prices:
                tier = dict(tier)
                tier["prices"] = clean_prices
                clean_tiers.append(tier)
            else:
                print(f"[VALIDATE] {pid}/{tier_name}: тир без валидных цен — отброшен")

        if clean_tiers:
            preset = dict(preset)
            preset["tiers"] = clean_tiers
            sanitized.append(preset)
        elif prev_preset:
            print(f"[VALIDATE] {pid}: все тиры невалидны в этом прогоне — оставляем предыдущую версию пресета целиком")
            sanitized.append(prev_preset)
        else:
            print(f"[VALIDATE] {pid}: все тиры невалидны и предыдущей версии нет — пресет пропущен")

    return sanitized
