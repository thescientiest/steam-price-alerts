# Steam Sale Alert Discord Bot

An automated Discord bot that tracks Steam games, lets users set custom discount and price thresholds, and delivers rich Discord Embed announcements whenever a tracked game goes on sale.

---

## Features

- **Slash Commands**:
  - `/track <url_or_appid> [min_discount] [target_price]`: Add a game to this server's watchlist with optional discount % or target price thresholds. Supports numeric AppIDs (e.g. `620`) or full Steam Store URLs (e.g. `https://store.steampowered.com/app/620/Portal_2/`).
  - `/untrack <url_or_appid>`: Remove a game from the watchlist.
  - `/list`: Display all games tracked by the server, their current prices, and discount status.
  - `/checknow`: Immediately check prices and list current deals without waiting for the next scheduled loop.
  - `/setchannel <#channel>`: Set the server channel where background sale announcements are posted (requires `Manage Channels` permission).
- **Automated Background Sale Alerts**:
  - Periodically checks Steam Store API for all tracked games.
  - Dispatches rich Discord Embeds containing game cover art, discount percentage, old vs new price, savings, and direct Steam links.
  - State tracking prevents duplicate spam: only alerts when a game newly goes on sale or deepens its discount.
- **Portable Database via SQLAlchemy**:
  - **Local SQLite (Default)**: Zero setup, zero recurring cost, fast single-file database (`steam_deals.db`).
  - **AWS RDS Portability**: Switch to AWS RDS (PostgreSQL/MySQL) anytime simply by setting `DATABASE_URL` in `.env`.

---

## Project Structure

```
├── bot.py                  # Main Discord bot client, slash commands & background loop
├── steam_client.py         # Steam Store API client, pricing parser, and URL extractor
├── models.py               # SQLAlchemy ORM models (TrackedGame, GuildSetting)
├── db.py                   # Database engine, session helpers, and CRUD queries
├── config.py               # Environment configuration loader
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment configuration template
├── tests/
│   ├── test_steam_client.py # Unit tests for AppID parsing & Steam API parser
│   └── test_db.py           # Unit tests for database models & operations
└── README.md               # Setup and usage documentation
```

---

## Quickstart & Setup Guide

### 1. Create a Discord Bot
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**.
2. Give your application a name (e.g., `Steam Sale Watcher`).
3. Navigate to the **Bot** tab on the left:
   - Click **Reset Token** to copy your **Bot Token**. Save this for your `.env` file.
4. Under **Privileged Gateway Intents**, standard intents are sufficient.
5. Navigate to **OAuth2 -> URL Generator**:
   - Under **Scopes**, check `bot` and `applications.commands`.
   - Under **Bot Permissions**, check:
     - `Send Messages`
     - `Embed Links`
     - `Use Application Commands`
     - `View Channels`
   - Copy the generated URL and open it in your browser to invite the bot to your Discord server.

---

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in your Discord Bot token:
```env
DISCORD_BOT_TOKEN=your_actual_bot_token_here
DATABASE_URL=sqlite:///steam_deals.db
CHECK_INTERVAL_HOURS=1
DEFAULT_CURRENCY=us
DEFAULT_COUNTRY=US
```

---

### 3. Install Dependencies
Make sure you have Python 3.10+ installed:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### 4. Verify System & Configuration
Run the built-in self-test to verify database initialization and Steam Store API connectivity:
```bash
python bot.py --verify-config
```

Run automated tests:
```bash
python -m unittest discover tests
```

---

### 5. Start the Bot
```bash
python bot.py
```
Once the bot is online, you will see:
```text
Logged in as Steam Sale Watcher (123456789012345678)
Synced 5 application slash commands.
Starting scheduled Steam price check...
```

---

## Switching to AWS RDS (Optional)

If you ever want to host the bot on cloud infrastructure (e.g., AWS EC2, ECS, or a VPS) and use an AWS RDS managed database:
1. Create a PostgreSQL or MySQL instance in AWS RDS.
2. Install the database driver (e.g., `pip install psycopg2-binary` for PostgreSQL).
3. In your `.env` file, change `DATABASE_URL`:
   ```env
   DATABASE_URL=postgresql+psycopg2://<db_user>:<db_password>@<rds_endpoint>:5432/<db_name>
   ```
4. Restart `python bot.py`. SQLAlchemy will automatically create tables and manage connections to AWS RDS!
