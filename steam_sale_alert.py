import os
import requests

# ==============================================================================
# Configuration
# ==============================================================================
# If using IsThereAnyDeal, set ITAD_API_KEY in your environment or paste below:
RAW_API_KEY = os.getenv("ITAD_API_KEY", "YOUR_ITAD_API_KEY")

# Automatically strip out hidden spaces, carriage returns, and non-ASCII artifacts
ITAD_API_KEY = "".join(char for char in RAW_API_KEY if char.isascii()).strip()


# ==============================================================================
# Method 1: Direct Steam Store API (Recommended - No API key required)
# ==============================================================================
def check_steam_sale_by_id(app_id, currency="us"):
    """
    Checks the current price and discount status of a game directly from
    Steam's official Store API. Does not require any third-party API key.
    """
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc={currency}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return f"Error: Steam API returned status {response.status_code}"

        payload = response.json().get(str(app_id), {})
        if not payload.get("success"):
            return f"Error: Could not retrieve Steam data for AppID: {app_id}."

        data = payload.get("data", {})
        game_title = data.get("name", f"AppID {app_id}")

        if data.get("is_free"):
            return f"Info: {game_title} is Free-to-Play on Steam."

        price_overview = data.get("price_overview")
        if not price_overview:
            return f"Info: {game_title} has no purchase pricing available on Steam."

        cut = price_overview.get("discount_percent", 0)
        current_price = price_overview.get("final_formatted")
        regular_price = price_overview.get("initial_formatted")
        buy_url = f"https://store.steampowered.com/app/{app_id}/"

        if cut > 0:
            return (
                f"SALE ON STEAM! {game_title} is {cut}% off!\n"
                f"Current Price: {current_price} (Regular: {regular_price})\n"
                f"Buy here: {buy_url}"
            )
        else:
            return (
                f"Info: {game_title} is currently full price on Steam ({current_price}).\n"
                f"Store page: {buy_url}"
            )

    except requests.exceptions.Timeout:
        return "Error: Request to Steam timed out."
    except requests.exceptions.JSONDecodeError:
        return "Error: Steam returned an unexpected non-JSON response."
    except Exception as e:
        return f"Error: An unexpected error occurred: {e}"


# ==============================================================================
# Method 2: IsThereAnyDeal API (v3) (Requires a valid ITAD API key)
# ==============================================================================
def check_steam_sale_itad(app_id, country="US"):
    """
    Looks up a Steam AppID on IsThereAnyDeal and checks active pricing/deals
    specifically for the Steam store using the ITAD v1 lookup and v3 price endpoints.
    """
    if not ITAD_API_KEY or "YOUR_ITAD_API_KEY" in ITAD_API_KEY:
        return "Error: Please add your IsThereAnyDeal API key to the script first!"

    # 1. ITAD v1 Game Lookup Endpoint
    lookup_url = "https://api.isthereanydeal.com/games/lookup/v1"
    try:
        lookup_response = requests.get(
            lookup_url,
            params={"key": ITAD_API_KEY, "appid": app_id},
            timeout=10
        )
        if lookup_response.status_code == 403:
            return "Error: ITAD API key is invalid or expired. Check your key at https://isthereanydeal.com/apps/my/"
        elif lookup_response.status_code != 200:
            return f"Error: Lookup failed. ITAD API returned status: {lookup_response.status_code}"

        lookup_data = lookup_response.json()
        if not lookup_data.get("found"):
            return f"Error: Could not find a game matching Steam AppID: {app_id} on ITAD."

        game_id = lookup_data["game"]["id"]
        game_title = lookup_data["game"]["title"]

        # 2. ITAD v3 Price Endpoint
        price_url = "https://api.isthereanydeal.com/games/prices/v3"
        price_response = requests.post(
            price_url,
            params={"key": ITAD_API_KEY, "country": country},
            json=[game_id],
            timeout=10
        )
        if price_response.status_code != 200:
            return f"Error: Price check failed. ITAD API returned status: {price_response.status_code}"

        price_data = price_response.json()
        if not price_data:
            return "Error: No price data returned from ITAD."

        # 3. Extract the Steam deal
        game_prices = next((item for item in price_data if item.get("id") == game_id), None)
        if not game_prices:
            return "Error: Target game ID data not found in ITAD response."

        deals = game_prices.get("deals", [])
        steam_deal = next((d for d in deals if d.get("shop", {}).get("name", "").lower() == "steam"), None)

        if steam_deal:
            current_price = steam_deal["price"]["amount"]
            regular_price = steam_deal["regular"]["amount"]
            cut = steam_deal["cut"]
            buy_url = steam_deal["url"]

            if cut > 0:
                return (
                    f"SALE ON STEAM! {game_title} is {cut}% off!\n"
                    f"Current Price: ${current_price} (Regular: ${regular_price})\n"
                    f"Buy here: {buy_url}"
                )
            else:
                return f"Info: {game_title} is currently full price on Steam (${regular_price})."
        else:
            return f"Error: {game_title} is tracked on ITAD, but no active pricing was found for Steam."

    except requests.exceptions.Timeout:
        return "Error: Request to ITAD timed out."
    except requests.exceptions.JSONDecodeError:
        return "Error: ITAD returned an unexpected non-JSON response."
    except Exception as e:
        return f"Error: An unexpected error occurred: {e}"


# ==============================================================================
# Example Run
# ==============================================================================
if __name__ == "__main__":
    # Test using Direct Steam API (No API key needed)
    print("--- Direct Steam API Check ---")
    print(check_steam_sale_by_id(730))      # Counter-Strike 2 (Free to play)
    print()
    print(check_steam_sale_by_id(620))      # Portal 2
    print()
    print(check_steam_sale_by_id(1091500))  # Cyberpunk 2077
