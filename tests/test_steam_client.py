import unittest
from unittest.mock import MagicMock, patch

from steam_client import SteamGameDetails, fetch_steam_game, parse_app_id


class TestSteamClient(unittest.TestCase):
    def test_parse_app_id_integers(self):
        self.assertEqual(parse_app_id(620), 620)
        self.assertEqual(parse_app_id("620"), 620)
        self.assertEqual(parse_app_id("  1091500  "), 1091500)
        self.assertIsNone(parse_app_id(-5))
        self.assertIsNone(parse_app_id(0))
        self.assertIsNone(parse_app_id("abc"))

    def test_parse_app_id_urls(self):
        self.assertEqual(
            parse_app_id("https://store.steampowered.com/app/620/Portal_2/"),
            620,
        )
        self.assertEqual(
            parse_app_id("http://store.steampowered.com/app/1091500/Cyberpunk_2077"),
            1091500,
        )
        self.assertEqual(
            parse_app_id("store.steampowered.com/app/730?snr=1_4_4__118"),
            730,
        )
        self.assertIsNone(parse_app_id("https://example.com/not_steam"))

    @patch("steam_client.requests.get")
    def test_fetch_steam_game_on_sale(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "620": {
                "success": True,
                "data": {
                    "name": "Portal 2",
                    "header_image": "https://cdn.akamai.steamstatic.com/steam/apps/620/header.jpg",
                    "is_free": False,
                    "price_overview": {
                        "discount_percent": 80,
                        "initial": 999,
                        "final": 199,
                        "initial_formatted": "$9.99",
                        "final_formatted": "$1.99",
                    },
                },
            }
        }
        mock_get.return_value = mock_response

        details = fetch_steam_game(620)
        self.assertIsNotNone(details)
        self.assertEqual(details.app_id, 620)
        self.assertEqual(details.title, "Portal 2")
        self.assertTrue(details.is_on_sale)
        self.assertEqual(details.discount_percent, 80)
        self.assertEqual(details.final_price_formatted, "$1.99")
        self.assertEqual(details.initial_price_formatted, "$9.99")

    @patch("steam_client.requests.get")
    def test_fetch_steam_game_free(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "730": {
                "success": True,
                "data": {
                    "name": "Counter-Strike 2",
                    "header_image": "https://cdn.akamai.steamstatic.com/steam/apps/730/header.jpg",
                    "is_free": True,
                },
            }
        }
        mock_get.return_value = mock_response

        details = fetch_steam_game(730)
        self.assertIsNotNone(details)
        self.assertTrue(details.is_free)
        self.assertFalse(details.is_on_sale)
        self.assertEqual(details.final_price_formatted, "Free")

    @patch("steam_client.requests.get")
    def test_fetch_steam_game_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"9999999": {"success": False}}
        mock_get.return_value = mock_response

        details = fetch_steam_game(9999999)
        self.assertIsNone(details)


if __name__ == "__main__":
    unittest.main()
