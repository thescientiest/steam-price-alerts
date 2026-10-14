from dataclasses import dataclass
import re
from typing import Optional
import requests


@dataclass
class SteamGameDetails:
    app_id: int
    title: str
    is_free: bool
    is_on_sale: bool
    discount_percent: int
    initial_price_formatted: str
    final_price_formatted: str
    initial_price_cents: int
    final_price_cents: int
    header_image_url: str
    store_url: str
    currency: str


def parse_app_id(query: str | int) -> Optional[int]:
    """
    Parses a Steam AppID from either:
    - Pure integer or string integer: 730 or "730"
    - Steam store URL: "https://store.steampowered.com/app/730/CounterStrike_2/"
    """
    if isinstance(query, int):
        return query if query > 0 else None

    cleaned = str(query).strip()
    if cleaned.isdigit():
        val = int(cleaned)
        return val if val > 0 else None

    # Match store URL pattern
    match = re.search(r"store\.steampowered\.com/app/(\d+)", cleaned, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None


def fetch_steam_game(app_id: int, currency: str = "us") -> Optional[SteamGameDetails]:
    """
    Fetches game details and pricing directly from Steam Store API.
    Returns SteamGameDetails or None if not found or on error.
    """
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc={currency}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None

        payload = response.json().get(str(app_id), {})
        if not payload.get("success"):
            return None

        data = payload.get("data", {})
        title = data.get("name", f"AppID {app_id}")
        header_image = data.get("header_image", "")
        store_url = f"https://store.steampowered.com/app/{app_id}/"

        if data.get("is_free"):
            return SteamGameDetails(
                app_id=app_id,
                title=title,
                is_free=True,
                is_on_sale=False,
                discount_percent=0,
                initial_price_formatted="Free",
                final_price_formatted="Free",
                initial_price_cents=0,
                final_price_cents=0,
                header_image_url=header_image,
                store_url=store_url,
                currency=currency.upper(),
            )

        price_overview = data.get("price_overview")
        if not price_overview:
            # Game exists but has no pricing (e.g. unreleased, delisted, hardware)
            return SteamGameDetails(
                app_id=app_id,
                title=title,
                is_free=False,
                is_on_sale=False,
                discount_percent=0,
                initial_price_formatted="N/A",
                final_price_formatted="N/A",
                initial_price_cents=0,
                final_price_cents=0,
                header_image_url=header_image,
                store_url=store_url,
                currency=currency.upper(),
            )

        discount_percent = int(price_overview.get("discount_percent", 0))
        final_price_formatted = price_overview.get("final_formatted", "N/A")
        initial_price_formatted = price_overview.get("initial_formatted", final_price_formatted)
        initial_cents = int(price_overview.get("initial", 0))
        final_cents = int(price_overview.get("final", 0))
        is_on_sale = discount_percent > 0

        return SteamGameDetails(
            app_id=app_id,
            title=title,
            is_free=False,
            is_on_sale=is_on_sale,
            discount_percent=discount_percent,
            initial_price_formatted=initial_price_formatted,
            final_price_formatted=final_price_formatted,
            initial_price_cents=initial_cents,
            final_price_cents=final_cents,
            header_image_url=header_image,
            store_url=store_url,
            currency=currency.upper(),
        )

    except Exception:
        return None
