import asyncio
import logging
import os
import sys
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    CHECK_INTERVAL_HOURS,
    DEFAULT_CURRENCY,
    DISCORD_BOT_TOKEN,
)
from db import (
    add_or_update_tracked_game,
    get_all_tracked_games,
    get_guild_channel,
    get_guild_tracked_games,
    init_db,
    remove_tracked_game,
    set_guild_channel,
    update_game_sale_state,
)
from steam_client import SteamGameDetails, fetch_steam_game, parse_app_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("SteamSaleBot")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def create_sale_embed(game_name: str, details: SteamGameDetails) -> discord.Embed:
    """Builds a rich Discord Embed for a detected Steam sale."""
    embed = discord.Embed(
        title=f"🔥 Steam Sale Alert: {game_name}!",
        url=details.store_url,
        color=0xE74C3C,  # Highlight sale red
        description=f"**[{details.title}]({details.store_url})** is now on sale on Steam!",
    )
    if details.header_image_url:
        embed.set_image(url=details.header_image_url)

    embed.add_field(name="Discount", value=f"**-{details.discount_percent}%**", inline=True)
    embed.add_field(name="Sale Price", value=f"**{details.final_price_formatted}**", inline=True)
    embed.add_field(name="Regular Price", value=f"~~{details.initial_price_formatted}~~", inline=True)

    embed.set_footer(text="Steam Sale Alert Bot • Click the title to open Steam")
    return embed


def create_game_info_embed(details: SteamGameDetails, min_discount: int, target_price: Optional[float]) -> discord.Embed:
    """Builds an embed confirming that a game has been added to tracking."""
    embed = discord.Embed(
        title=f"🎮 Tracking: {details.title}",
        url=details.store_url,
        color=0x2ECC71 if details.is_on_sale else 0x1B2838,
        description=f"Successfully added to this server's Steam watchlist.",
    )
    if details.header_image_url:
        embed.set_thumbnail(url=details.header_image_url)

    status_str = f"On Sale (-{details.discount_percent}%)" if details.is_on_sale else "Regular Price"
    embed.add_field(name="Current Price", value=f"{details.final_price_formatted} ({status_str})", inline=False)

    threshold_str = "Any sale"
    if min_discount > 0 and target_price:
        threshold_str = f"At least {min_discount}% off AND price <= ${target_price:.2f}"
    elif min_discount > 0:
        threshold_str = f"At least {min_discount}% off"
    elif target_price:
        threshold_str = f"Price <= ${target_price:.2f}"

    embed.add_field(name="Alert Trigger", value=threshold_str, inline=True)
    embed.add_field(name="Steam AppID", value=str(details.app_id), inline=True)
    return embed


@tasks.loop(hours=CHECK_INTERVAL_HOURS)
async def check_sales_loop():
    """Background task that periodically scans Steam for discounts on tracked games."""
    logger.info("Starting scheduled Steam price check...")
    try:
        tracked_records = get_all_tracked_games()
        if not tracked_records:
            logger.info("No games currently tracked across servers.")
            return

        # Cache Steam API lookups by app_id so multiple guilds tracking the same game share 1 call
        price_cache: dict[int, Optional[SteamGameDetails]] = {}
        unique_app_ids = set(record.app_id for record in tracked_records)

        for app_id in unique_app_ids:
            price_cache[app_id] = fetch_steam_game(app_id, currency=DEFAULT_CURRENCY)
            # Polite delay to prevent Steam rate limits
            await asyncio.sleep(1.5)

        for record in tracked_records:
            details = price_cache.get(record.app_id)
            if not details:
                continue

            current_cents = details.final_price_cents
            meets_discount = details.discount_percent >= record.min_discount
            meets_price = True
            if record.target_price is not None:
                meets_price = (current_cents <= (record.target_price * 100))

            sale_active = details.is_on_sale and meets_discount and meets_price

            if sale_active:
                # Trigger alert if newly on sale OR if discount deepened
                is_new_sale = not record.is_on_sale
                is_deeper_discount = details.discount_percent > record.last_discount

                if is_new_sale or is_deeper_discount:
                    # Determine target channel
                    channel_id = record.channel_id or get_guild_channel(record.guild_id)
                    if channel_id:
                        channel = bot.get_channel(channel_id)
                        if channel:
                            embed = create_sale_embed(record.game_name, details)
                            try:
                                await channel.send(embed=embed)
                                logger.info(
                                    f"Dispatched alert for {record.game_name} to channel {channel_id} (Guild: {record.guild_id})"
                                )
                            except Exception as e:
                                logger.error(f"Failed to send alert to channel {channel_id}: {e}")

                    # Update DB state
                    update_game_sale_state(
                        game_id=record.id,
                        is_on_sale=True,
                        last_discount=details.discount_percent,
                        last_final_price=details.final_price_formatted,
                    )
            else:
                # Sale ended or game not meeting criteria
                if record.is_on_sale:
                    update_game_sale_state(
                        game_id=record.id,
                        is_on_sale=False,
                        last_discount=details.discount_percent,
                        last_final_price=details.final_price_formatted,
                    )

        logger.info("Completed scheduled Steam price check.")
    except Exception as e:
        logger.error(f"Unexpected error in check_sales_loop: {e}", exc_info=True)


@check_sales_loop.before_loop
async def before_check_sales():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} application slash commands.")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")

    if not check_sales_loop.is_running():
        check_sales_loop.start()


# ==============================================================================
# Slash Commands
# ==============================================================================


@bot.tree.command(name="track", description="Track a Steam game by AppID or Steam store URL.")
@app_commands.describe(
    game="Steam AppID (e.g. 620) or full store URL",
    min_discount="Alert only if discount % is at least this high (e.g. 50 for 50%+ off)",
    target_price="Alert only if price drops to or below this amount in dollars (e.g. 19.99)",
)
async def track(
    interaction: discord.Interaction,
    game: str,
    min_discount: Optional[int] = 0,
    target_price: Optional[float] = None,
):
    await interaction.response.defer()

    if not interaction.guild_id:
        await interaction.followup.send("This command must be used within a server.", ephemeral=True)
        return

    app_id = parse_app_id(game)
    if not app_id:
        await interaction.followup.send(
            "❌ Could not recognize a valid Steam AppID or URL. Example: `/track 620` or `/track https://store.steampowered.com/app/620/Portal_2/`",
            ephemeral=True,
        )
        return

    details = fetch_steam_game(app_id, currency=DEFAULT_CURRENCY)
    if not details:
        await interaction.followup.send(
            f"❌ Could not retrieve game data from Steam for AppID `{app_id}`. Please verify the ID or URL.",
            ephemeral=True,
        )
        return

    min_disc = max(0, min(100, min_discount or 0))

    add_or_update_tracked_game(
        guild_id=interaction.guild_id,
        app_id=app_id,
        game_name=details.title,
        channel_id=interaction.channel_id,
        header_image=details.header_image_url,
        min_discount=min_disc,
        target_price=target_price,
        added_by_user_id=interaction.user.id,
        current_discount=details.discount_percent,
        current_final_price=details.final_price_formatted,
        is_on_sale=details.is_on_sale,
    )

    embed = create_game_info_embed(details, min_disc, target_price)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="untrack", description="Stop tracking a Steam game.")
@app_commands.describe(game="Steam AppID or full store URL")
async def untrack(interaction: discord.Interaction, game: str):
    await interaction.response.defer()

    if not interaction.guild_id:
        await interaction.followup.send("This command must be used within a server.", ephemeral=True)
        return

    app_id = parse_app_id(game)
    if not app_id:
        await interaction.followup.send("❌ Could not recognize a valid Steam AppID or URL.", ephemeral=True)
        return

    removed = remove_tracked_game(interaction.guild_id, app_id)
    if removed:
        await interaction.followup.send(f"✅ Removed Steam AppID `{app_id}` from this server's watchlist.")
    else:
        await interaction.followup.send(f"⚠️ AppID `{app_id}` was not found in this server's watchlist.", ephemeral=True)


@bot.tree.command(name="list", description="List all Steam games tracked in this server.")
async def list_tracked(interaction: discord.Interaction):
    await interaction.response.defer()

    if not interaction.guild_id:
        await interaction.followup.send("This command must be used within a server.", ephemeral=True)
        return

    games = get_guild_tracked_games(interaction.guild_id)
    if not games:
        await interaction.followup.send(
            "ℹ️ No games are currently tracked in this server. Use `/track <url_or_appid>` to add one!",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title=f"📋 Tracked Steam Games ({len(games)})",
        color=0x1B2838,
        description="Here are the games currently monitored for sale alerts:",
    )

    for g in games[:25]:  # Discord embed field limit safety
        sale_badge = f"🔥 **SALE (-{g.last_discount}%)**" if g.is_on_sale else "Full Price"
        price_str = g.last_final_price or "N/A"
        thresh_parts = []
        if g.min_discount > 0:
            thresh_parts.append(f"Min: {g.min_discount}% off")
        if g.target_price is not None:
            thresh_parts.append(f"Target: ${g.target_price:.2f}")
        thresh_info = f" ({', '.join(thresh_parts)})" if thresh_parts else ""

        embed.add_field(
            name=f"{g.game_name} (`{g.app_id}`)",
            value=f"Price: {price_str} • {sale_badge}{thresh_info}\n[Steam Page](https://store.steampowered.com/app/{g.app_id}/)",
            inline=False,
        )

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="checknow", description="Immediately checks all tracked games for active sales.")
async def checknow(interaction: discord.Interaction):
    await interaction.response.defer()

    if not interaction.guild_id:
        await interaction.followup.send("This command must be used within a server.", ephemeral=True)
        return

    games = get_guild_tracked_games(interaction.guild_id)
    if not games:
        await interaction.followup.send("ℹ️ No games are currently tracked. Use `/track` first.", ephemeral=True)
        return

    active_deals = []
    for g in games:
        details = fetch_steam_game(g.app_id, currency=DEFAULT_CURRENCY)
        if details and details.is_on_sale:
            active_deals.append((g, details))
        await asyncio.sleep(0.5)

    if not active_deals:
        await interaction.followup.send("ℹ️ None of the games currently tracked in this server are on sale.")
        return

    embed = discord.Embed(
        title=f"🔥 Active Deals Found ({len(active_deals)})",
        color=0xE74C3C,
        description="The following tracked games currently have discounts on Steam:",
    )
    for g, details in active_deals[:10]:
        embed.add_field(
            name=f"{details.title} (-{details.discount_percent}%)",
            value=f"Now **{details.final_price_formatted}** (was ~~{details.initial_price_formatted}~~)\n[Store Page]({details.store_url})",
            inline=False,
        )

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="setchannel", description="Set the default channel for Steam sale alert announcements.")
@app_commands.describe(channel="The channel where sale alerts should be sent")
@app_commands.checks.has_permissions(manage_channels=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild_id:
        await interaction.response.send_message("This command must be used within a server.", ephemeral=True)
        return

    set_guild_channel(interaction.guild_id, channel.id)
    await interaction.response.send_message(
        f"✅ Sale alert announcements for this server will now be posted in {channel.mention}.",
        ephemeral=True,
    )


@setchannel.error
async def setchannel_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You need the **Manage Channels** permission to change the alert channel.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(f"❌ Error setting alert channel: {error}", ephemeral=True)


# ==============================================================================
# Main Entry Point & CLI Verification
# ==============================================================================


def start_health_check_server():
    """
    If running on Render (or any cloud host) as a Web Service, Render requires
    binding to the port specified in the PORT environment variable.
    This starts a lightweight background HTTP server so health checks pass.
    """
    port_str = os.getenv("PORT")
    if not port_str:
        return

    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import threading

        port = int(port_str)

        class HealthCheckHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Steam Sale Discord Bot is online and healthy!\n")

            def log_message(self, format, *args):
                pass  # Suppress health check logging spam

        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Health check HTTP server listening on port {port} for Render deployment.")
    except Exception as e:
        logger.warning(f"Could not start health check HTTP server: {e}")


def run_bot():
    init_db()

    if "--verify-config" in sys.argv:
        print("=== Steam Sale Alert Bot Self-Check ===")
        print("✓ Database tables initialized successfully.")
        test_game = fetch_steam_game(620)  # Portal 2
        if test_game:
            print(f"✓ Steam Store API reachable: Found '{test_game.title}' (Price: {test_game.final_price_formatted})")
        else:
            print("⚠ Steam Store API did not return expected response for Portal 2.")

        if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_discord_bot_token_here":
            print("ℹ Note: DISCORD_BOT_TOKEN is not yet set in .env. Bot gateway connection skipped.")
            print("Self-check completed successfully.")
            return

        print("✓ DISCORD_BOT_TOKEN is configured.")
        print("Self-check completed successfully.")
        return

    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_discord_bot_token_here":
        logger.error(
            "DISCORD_BOT_TOKEN is not set! Please copy .env.example to .env and insert your bot token."
        )
        sys.exit(1)

    start_health_check_server()
    logger.info("Starting Discord bot...")
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run_bot()
