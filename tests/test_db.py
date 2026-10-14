import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db
from models import Base


class TestDatabaseOperations(unittest.TestCase):
    def setUp(self):
        # Use an isolated in-memory SQLite database for test suite
        self.test_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.test_engine)
        self.TestSession = sessionmaker(bind=self.test_engine, autoflush=False, expire_on_commit=False)

        # Patch db module session and engine
        self._orig_engine = db.engine
        self._orig_session = db.SessionLocal
        db.engine = self.test_engine
        db.SessionLocal = self.TestSession

    def tearDown(self):
        Base.metadata.drop_all(bind=self.test_engine)
        db.engine = self._orig_engine
        db.SessionLocal = self._orig_session

    def test_add_and_get_tracked_game(self):
        game = db.add_or_update_tracked_game(
            guild_id=12345,
            app_id=620,
            game_name="Portal 2",
            channel_id=98765,
            header_image="https://example.com/portal2.jpg",
            min_discount=50,
            target_price=4.99,
            added_by_user_id=111,
            current_discount=0,
            current_final_price="$9.99",
            is_on_sale=False,
        )
        self.assertEqual(game.app_id, 620)
        self.assertEqual(game.game_name, "Portal 2")

        games = db.get_guild_tracked_games(guild_id=12345)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].app_id, 620)
        self.assertEqual(games[0].min_discount, 50)
        self.assertEqual(games[0].target_price, 4.99)

    def test_update_existing_tracked_game(self):
        db.add_or_update_tracked_game(
            guild_id=12345,
            app_id=620,
            game_name="Portal 2",
            min_discount=0,
        )

        # Update threshold
        db.add_or_update_tracked_game(
            guild_id=12345,
            app_id=620,
            game_name="Portal 2",
            min_discount=75,
        )

        games = db.get_guild_tracked_games(guild_id=12345)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].min_discount, 75)

    def test_remove_tracked_game(self):
        db.add_or_update_tracked_game(
            guild_id=12345,
            app_id=620,
            game_name="Portal 2",
        )
        removed = db.remove_tracked_game(guild_id=12345, app_id=620)
        self.assertTrue(removed)

        games = db.get_guild_tracked_games(guild_id=12345)
        self.assertEqual(len(games), 0)

        # Removing non-existent returns False
        removed_again = db.remove_tracked_game(guild_id=12345, app_id=620)
        self.assertFalse(removed_again)

    def test_guild_channel_settings(self):
        self.assertIsNone(db.get_guild_channel(guild_id=12345))

        db.set_guild_channel(guild_id=12345, channel_id=55555)
        self.assertEqual(db.get_guild_channel(guild_id=12345), 55555)

        # Update channel
        db.set_guild_channel(guild_id=12345, channel_id=66666)
        self.assertEqual(db.get_guild_channel(guild_id=12345), 66666)

    def test_update_game_sale_state(self):
        game = db.add_or_update_tracked_game(
            guild_id=12345,
            app_id=620,
            game_name="Portal 2",
            current_discount=0,
            is_on_sale=False,
        )

        db.update_game_sale_state(
            game_id=game.id,
            is_on_sale=True,
            last_discount=80,
            last_final_price="$1.99",
        )

        updated_games = db.get_guild_tracked_games(guild_id=12345)
        self.assertTrue(updated_games[0].is_on_sale)
        self.assertEqual(updated_games[0].last_discount, 80)
        self.assertEqual(updated_games[0].last_final_price, "$1.99")


if __name__ == "__main__":
    unittest.main()
