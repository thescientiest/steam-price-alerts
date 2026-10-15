import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Ensure the root project directory is in the Python module search path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steam_sale_alert import (
    check_and_notify_games,
    get_steam_game_details,
    check_steam_sale_by_id,
)


class handler(BaseHTTPRequestHandler):
    """
    Vercel Serverless Function entrypoint.
    Handles GET and POST requests to check Steam sales and dispatch alerts.
    """

    def _send_json_response(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)

        # 1. Determine which Steam App IDs to check
        raw_ids = params.get("app_ids", [])
        if not raw_ids:
            single_id = params.get("app_id", [])
            raw_ids = single_id if single_id else []

        # If not supplied in query params, fall back to TRACKED_APP_IDS env var, or default to 620 & 1091500
        if raw_ids:
            # Handle comma-separated lists like ?app_ids=620,1091500
            app_id_list = []
            for item in raw_ids:
                app_id_list.extend([x.strip() for x in item.split(",") if x.strip()])
        else:
            env_ids = os.getenv("TRACKED_APP_IDS", "620,1091500")
            app_id_list = [x.strip() for x in env_ids.split(",") if x.strip()]

        # Convert to integers
        valid_app_ids = []
        for x in app_id_list:
            try:
                valid_app_ids.append(int(x))
            except ValueError:
                continue

        if not valid_app_ids:
            self._send_json_response(400, {
                "success": False,
                "error": "No valid numeric Steam App IDs provided."
            })
            return

        # 2. Check notification settings
        # By default, notifications are sent if webhook credentials are configured
        should_notify = params.get("notify", ["true"])[0].lower() in ("true", "1", "yes")

        discord_url = params.get("discord_webhook", [None])[0]
        tg_token = params.get("telegram_token", [None])[0]
        tg_chat = params.get("telegram_chat_id", [None])[0]

        # 3. Process game sale checks & trigger webhooks if on sale
        results = check_and_notify_games(
            app_ids=valid_app_ids,
            discord_webhook=discord_url,
            telegram_token=tg_token,
            telegram_chat_id=tg_chat,
            notify_only_on_sale=True
        )

        sales_found = [r for r in results if r.get("is_sale")]

        self._send_json_response(200, {
            "success": True,
            "total_checked": len(results),
            "sales_count": len(sales_found),
            "games": results,
            "help": {
                "usage": "Pass ?app_id=620 or ?app_ids=620,1091500 in the query parameters.",
                "cron_compatible": True
            }
        })

    def do_POST(self):
        # Allow triggering via POST (e.g. from GitHub Actions, webhooks, or dashboards)
        self.do_GET()
