import os
import requests

# ==============================================================================
# Configuration
# ==============================================================================
# If using IsThereAnyDeal, set ITAD_API_KEY in your environment or paste below:
RAW_API_KEY = os.getenv("ITAD_API_KEY", "YOUR_ITAD_API_KEY")
ITAD_API_KEY = "".join(char for char in RAW_API_KEY if char.isascii()).strip()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


# ==============================================================================
# Method 1: Direct Steam Store API (Recommended - No API key required)
# ==============================================================================
def get_steam_game_details(app_id, currency="us"):
    """
    Fetches structured details and pricing for a Steam App ID directly from
    the Steam Store API.
    Returns a dictionary with parsed status and pricing fields.
    """
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc={currency}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return {
                "success": False,
                "app_id": app_id,
                "error": f"Steam API returned status {response.status_code}"
            }

        payload = response.json().get(str(app_id), {})
        if not payload.get("success"):
            return {
                "success": False,
                "app_id": app_id,
                "error": f"Could not retrieve Steam data for AppID: {app_id}."
            }

        data = payload.get("data", {})
        title = data.get("name", f"AppID {app_id}")
        is_free = bool(data.get("is_free"))
        header_image = data.get("header_image", "")
        buy_url = f"https://store.steampowered.com/app/{app_id}/"

        if is_free:
            return {
                "success": True,
                "app_id": app_id,
                "title": title,
                "is_free": True,
                "is_sale": False,
                "discount_percent": 0,
                "initial_price": "Free",
                "final_price": "Free",
                "buy_url": buy_url,
                "header_image": header_image,
                "message": f"Info: {title} is Free-to-Play on Steam."
            }

        price_overview = data.get("price_overview")
        if not price_overview:
            return {
                "success": True,
                "app_id": app_id,
                "title": title,
                "is_free": False,
                "is_sale": False,
                "discount_percent": 0,
                "initial_price": None,
                "final_price": None,
                "buy_url": buy_url,
                "header_image": header_image,
                "message": f"Info: {title} has no purchase pricing available on Steam."
            }

        cut = price_overview.get("discount_percent", 0)
        current_price = price_overview.get("final_formatted", "")
        regular_price = price_overview.get("initial_formatted", "") or current_price
        is_sale = cut > 0

        if is_sale:
            msg = (
                f"SALE ON STEAM! {title} is {cut}% off!\n"
                f"Current Price: {current_price} (Regular: {regular_price})\n"
                f"Buy here: {buy_url}"
            )
        else:
            msg = (
                f"Info: {title} is currently full price on Steam ({current_price}).\n"
                f"Store page: {buy_url}"
            )

        return {
            "success": True,
            "app_id": app_id,
            "title": title,
            "is_free": False,
            "is_sale": is_sale,
            "discount_percent": cut,
            "initial_price": regular_price,
            "final_price": current_price,
            "buy_url": buy_url,
            "header_image": header_image,
            "message": msg
        }

    except requests.exceptions.Timeout:
        return {"success": False, "app_id": app_id, "error": "Steam request timed out."}
    except requests.exceptions.JSONDecodeError:
        return {"success": False, "app_id": app_id, "error": "Steam returned invalid JSON."}
    except Exception as e:
        return {"success": False, "app_id": app_id, "error": str(e)}


def check_steam_sale_by_id(app_id, currency="us"):
    """
    Convenience wrapper returning a human-readable text message.
    """
    details = get_steam_game_details(app_id, currency=currency)
    if details.get("success"):
        return details.get("message", "")
    return f"Error: {details.get('error', 'Unknown error')}"


# ==============================================================================
# Webhook Notifications (Discord & Telegram)
# ==============================================================================
def send_discord_alert(webhook_url, game_data):
    """
    Sends a rich Discord embed notification for a game sale.
    """
    if not webhook_url:
        return {"sent": False, "error": "No Discord webhook URL provided."}

    title = game_data.get("title", "Steam Game")
    cut = game_data.get("discount_percent", 0)
    current_price = game_data.get("final_price", "N/A")
    regular_price = game_data.get("initial_price", "N/A")
    buy_url = game_data.get("buy_url", "https://store.steampowered.com")
    header_image = game_data.get("header_image")

    embed = {
        "title": f"🚨 {title} is {cut}% off on Steam!",
        "url": buy_url,
        "color": 0x2ECC71 if cut >= 50 else 0x3498DB,
        "fields": [
            {"name": "Current Price", "value": f"**{current_price}**", "inline": True},
            {"name": "Regular Price", "value": f"~~{regular_price}~~", "inline": True},
            {"name": "Discount", "value": f"**-{cut}%**", "inline": True},
        ],
        "footer": {"text": "Steam Sale Alert Bot"},
    }
    if header_image:
        embed["image"] = {"url": header_image}

    payload = {
        "content": f"🎉 **Steam Sale Alert**: **{title}** is currently on sale for **{current_price}** (-{cut}%)!",
        "embeds": [embed]
    }

    try:
        res = requests.post(webhook_url, json=payload, timeout=10)
        return {"sent": res.status_code in (200, 204), "status_code": res.status_code}
    except Exception as e:
        return {"sent": False, "error": str(e)}


def send_telegram_alert(bot_token, chat_id, game_data):
    """
    Sends a Telegram notification for a game sale.
    """
    if not bot_token or not chat_id:
        return {"sent": False, "error": "Missing Telegram bot token or chat ID."}

    title = game_data.get("title", "Steam Game")
    cut = game_data.get("discount_percent", 0)
    current_price = game_data.get("final_price", "N/A")
    regular_price = game_data.get("initial_price", "N/A")
    buy_url = game_data.get("buy_url", "https://store.steampowered.com")

    text = (
        f"🚨 <b>Steam Sale Alert!</b>\n\n"
        f"🎮 <b>{title}</b> is <b>{cut}% OFF</b>!\n"
        f"💰 <b>Current:</b> {current_price} (Regular: <s>{regular_price}</s>)\n"
        f"🔗 <a href='{buy_url}'>View on Steam Store</a>"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        return {"sent": res.status_code == 200, "status_code": res.status_code}
    except Exception as e:
        return {"sent": False, "error": str(e)}


def check_and_notify_games(app_ids, discord_webhook=None, telegram_token=None, telegram_chat_id=None, notify_only_on_sale=True):
    """
    Checks an array of Steam App IDs, collects details, and sends webhook alerts
    if a sale is active.
    """
    discord_url = discord_webhook or DISCORD_WEBHOOK_URL
    tg_token = telegram_token or TELEGRAM_BOT_TOKEN
    tg_chat = telegram_chat_id or TELEGRAM_CHAT_ID

    results = []
    for app_id in app_ids:
        details = get_steam_game_details(app_id)
        notification_status = {}

        if details.get("success") and (details.get("is_sale") or not notify_only_on_sale):
            if discord_url:
                notification_status["discord"] = send_discord_alert(discord_url, details)
            if tg_token and tg_chat:
                notification_status["telegram"] = send_telegram_alert(tg_token, tg_chat, details)

        details["notifications"] = notification_status
        results.append(details)

    return results


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
    print("--- Direct Steam API Check ---")
    print(check_steam_sale_by_id(730))      # Counter-Strike 2 (Free to play)
    print()
    print(check_steam_sale_by_id(620))      # Portal 2
    print()
    print(check_steam_sale_by_id(1091500))  # Cyberpunk 2077
