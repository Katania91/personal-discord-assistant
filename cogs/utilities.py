import discord
from discord import app_commands
from discord.ext import commands
import datetime
import time
import random
import string
import io
import aiohttp
import asyncio
import logging
from utils import common, config, security

logger = logging.getLogger("discordbot")

class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="remindme", description="Set a reminder: 30s, 10m, 2h, 1d")
    async def remindme(self, interaction: discord.Interaction, time_str: str, message: str):
        if not await security.ensure_owner(interaction): return
        delta = common.parse_time(time_str)
        if not delta:
            await interaction.response.send_message("❌ Invalid time format. Use: 30s, 10m, 2h, 1d.", ephemeral=True)
            return
        try:
            reminder_time = datetime.datetime.now() + delta
            job_id = f"reminder_{interaction.user.id}_{int(time.time())}"
            self.bot.scheduler.add_job(self.send_single_reminder, 'date', run_date=reminder_time, args=[interaction.user.id, message], id=job_id)
            
            if delta.total_seconds() < 60:
                duration_str = f"{int(delta.total_seconds())} seconds"
            elif delta.total_seconds() < 3600:
                duration_str = f"{int(delta.total_seconds() // 60)} minutes"
            elif delta.total_seconds() < 86400:
                duration_str = f"{int(delta.total_seconds() // 3600)} hours"
            else:
                duration_str = f"{int(delta.days)} days"
                
            await interaction.response.send_message(f"✅ Reminder set in {duration_str}.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash remindme: {e}")
            await interaction.response.send_message("❌ Error setting reminder.", ephemeral=True)

    @app_commands.command(name="weather", description="Weather for a city (e.g. 'London, UK' or 'New York')")
    async def weather(self, interaction: discord.Interaction, location: str):
        if not await security.ensure_owner(interaction): return

        await interaction.response.defer(ephemeral=True)

        if ',' in location:
            parts = [part.strip() for part in location.split(',')]
            city = parts[0]
            country = parts[1] if len(parts) > 1 else ""
            search_query = f"{city}, {country}"
        else:
            city = location.strip()
            country = ""
            search_query = city

        async with aiohttp.ClientSession() as session:
            geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
            params = {'name': search_query, 'count': 5, 'language': 'en', 'format': 'json'}
            try:
                async with session.get(geocoding_url, params=params) as response:
                    if response.status != 200:
                        await interaction.followup.send(f"❌ Geocoding error ({response.status}).", ephemeral=True)
                        return
                    data = await response.json()
                    if not data.get('results'):
                        await interaction.followup.send(f"❌ Location '{location}' not found.", ephemeral=True)
                        return

                    best_match = None
                    if country:
                        for result in data['results']:
                            if country.lower() in result.get('country', '').lower():
                                best_match = result
                                break
                    if not best_match:
                        best_match = data['results'][0]

                    lat, lon = best_match['latitude'], best_match['longitude']
                    full_name = best_match['name']
                    if 'country' in best_match:
                        full_name += f", {best_match['country']}"
                    if 'admin1' in best_match and best_match['admin1']:
                        full_name += f" ({best_match['admin1']})"

                meteo_url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    'latitude': lat, 'longitude': lon,
                    'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m',
                    'daily': 'weather_code,temperature_2m_max,temperature_2m_min',
                    'timezone': 'auto'
                }
                async with session.get(meteo_url, params=params) as response:
                    if response.status != 200:
                        await interaction.followup.send(f"❌ Weather API error ({response.status}).", ephemeral=True)
                        return
                    meteo_data = await response.json()
                    current = meteo_data['current']
                    daily = meteo_data['daily']

                    emoji, desc = common.get_weather_description(current['weather_code'])
                    wind_dir = common.get_wind_direction(current.get('wind_direction_10m'))

                    embed = discord.Embed(
                        title=f"{emoji} Weather for {full_name}",
                        description=f"**{desc}**",
                        color=discord.Color.teal(),
                        timestamp=datetime.datetime.now()
                    )
                    embed.add_field(name="🌡️ Temperature", value=f"{current['temperature_2m']}°C\n(Feels like: {current['apparent_temperature']}°C)", inline=True)
                    embed.add_field(name="💧 Humidity", value=f"{current['relative_humidity_2m']}%", inline=True)
                    embed.add_field(name="💨 Wind", value=f"{current['wind_speed_10m']} km/h ({wind_dir})", inline=True)
                    embed.add_field(name="📈 Max / Min 📉", value=f"{daily['temperature_2m_max'][0]}°C / {daily['temperature_2m_min'][0]}°C", inline=True)
                    embed.set_footer(text="Data from Open-Meteo.com")
                    await interaction.followup.send(embed=embed, ephemeral=True)

            except aiohttp.ClientError as e:
                logger.exception(f"AIOHTTP Error: {e}")
                await interaction.followup.send("❌ Connection problem with weather services.", ephemeral=True)
            except Exception as e:
                logger.exception(f"Error slash weather: {e}")
                await interaction.followup.send("❌ Unexpected error in weather command.", ephemeral=True)

    @app_commands.command(name="password", description="Generate a password or passphrase")
    async def password(self, interaction: discord.Interaction, length: int = 16, phrase: bool = False, nospecial: bool = False):
        if not await security.ensure_owner(interaction): return

        await interaction.response.defer(ephemeral=True)

        try:
            if phrase:
                if not 3 <= length <= 10:
                    await interaction.followup.send("❌ For `phrase` mode, word count must be between 3 and 10.", ephemeral=True)
                    return
                wordlist = [
                    "crystal", "melody", "storm", "enigma", "aurora", "mystery", "serenade", "abyss", "spiral", "lightning",
                    "prism", "echo", "nebula", "vertex", "ocean", "mirror", "refuge", "labyrinth", "waterfall", "vortex",
                    "zenith", "oracle", "path", "phoenix", "serpent", "diamond", "shadow", "symphony", "volcano", "galaxy",
                    "mirage", "destiny", "eternity", "paradox", "chimera", "infinity", "reflection", "blizzard"
                ]
                pwd = '-'.join(random.choices(wordlist, k=length))
                title = f"🔑 Passphrase ({length} words)"
            else:
                if not 8 <= length <= 128:
                    await interaction.followup.send("❌ Password length must be between 8 and 128.", ephemeral=True)
                    return
                chars = string.ascii_letters + string.digits
                if not nospecial:
                    chars += string.punctuation
                pwd = ''.join(random.choice(chars) for _ in range(length))
                title = f"🔑 Random Password ({length} chars)"

            embed = discord.Embed(title=title, description=f"Here is your secure password:\n`{pwd}`", color=discord.Color.dark_green())
            embed.set_footer(text="⚠️ This message is visible only to you")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash password: {e}")
            await interaction.followup.send("❌ Error generating password.", ephemeral=True)

    @app_commands.command(name="qr", description="Generate a QR code from text")
    async def qr(self, interaction: discord.Interaction, text: str):
        if not await security.ensure_owner(interaction): return

        if len(text) > 500:
            await interaction.response.send_message("❌ Text too long for QR code (max 500 chars).", ephemeral=True)
            return
        try:
            await interaction.response.defer(ephemeral=True)
            qr_data = await common.generate_qr_code(text)
            if qr_data:
                embed = discord.Embed(
                    title="📱 QR Code Generated",
                    description=f"QR code for: `{text[:100]}{'...' if len(text) > 100 else ''}`",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now()
                )
                file_qr = discord.File(io.BytesIO(qr_data), filename="qrcode.png")
                embed.set_image(url="attachment://qrcode.png")
                embed.set_footer(text="Scan with your smartphone camera")
                await interaction.followup.send(embed=embed, file=file_qr, ephemeral=True)
            else:
                await interaction.followup.send("❌ Error generating QR code.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash qr: {e}")
            await interaction.response.send_message("❌ Error generating QR code.", ephemeral=True)

    @app_commands.command(name="shorten", description="Shorten a URL using is.gd")
    async def shorten(self, interaction: discord.Interaction, url: str):
        if not await security.ensure_owner(interaction): return
        if not (url.startswith('http://') or url.startswith('https://')):
            await interaction.response.send_message("❌ Invalid URL. Must start with `http://` or `https://`", ephemeral=True)
            return
        try:
            await interaction.response.defer(ephemeral=True)
            short_url = await common.shorten_url(url)
            if short_url:
                saved = len(url) - len(short_url)
                embed = discord.Embed(title="🔗 URL Shortened", color=discord.Color.green(), timestamp=datetime.datetime.now())
                embed.add_field(name="📎 Original URL", value=f"```{url[:100]}{'...' if len(url) > 100 else ''}```", inline=False)
                embed.add_field(name="✨ Shortened URL", value=f"**{short_url}**", inline=False)
                embed.add_field(
                    name="📊 Stats",
                    value=f"• Characters saved: **{saved}**\n• Original length: {len(url)}\n• Final length: {len(short_url)}",
                    inline=False
                )
                embed.set_footer(text="Service: is.gd")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("❌ Error shortening URL. Verify it is valid.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash shorten: {e}")
            await interaction.response.send_message("❌ Error shortening URL.", ephemeral=True)

    @app_commands.command(name="pomodoro", description="Start a Pomodoro timer (minutes, cycles)")
    async def pomodoro(self, interaction: discord.Interaction, minutes: int = 25, cycles: int = 1, label: str = None, notify_channel: bool = False):
        if not await security.ensure_owner(interaction): return
        if minutes <= 0 or cycles <= 0:
            await interaction.response.send_message("Invalid values for minutes/cycles.", ephemeral=True)
            return
        await interaction.response.send_message(f"⏱️ Starting Pomodoro: {minutes}min x {cycles} cycle(s){(' - '+label) if label else ''}", ephemeral=True)

        async def _runner(user_id, minutes, cycles, label, notify_channel):
            try:
                for i in range(1, cycles + 1):
                    await asyncio.sleep(minutes * 60)
                    usr = await self.bot.fetch_user(user_id)
                    txt = f"🔔 Pomodoro finished ({i}/{cycles})" + (f" - {label}" if label else "")
                    try:
                        await usr.send(txt)
                    except Exception:
                        logger.warning("Cannot send DM for pomodoro")
                    if notify_channel:
                        try:
                            ch = await self.bot.fetch_channel(config.REMINDER_CHANNEL_ID)
                            await ch.send(f"🔔 <@{user_id}> {txt}")
                        except Exception:
                            logger.exception("Cannot notify channel for pomodoro")
            except asyncio.CancelledError:
                logger.info("Pomodoro cancelled")
            except Exception:
                logger.exception("Error running Pomodoro")

        asyncio.create_task(_runner(interaction.user.id, minutes, cycles, label, notify_channel))

    async def send_single_reminder(self, user_id, message):
        """Sends a single reminder (used by scheduler)."""
        try:
            user = await self.bot.fetch_user(user_id)
            embed = discord.Embed(
                title="⏰ REMINDER!",
                description=message,
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now()
            )
            embed.set_footer(text="Reminder set with !remindme")
            await user.send(embed=embed)
            logger.info(f"Reminder sent to {user.name}: {message}")
            try:
                channel = await self.bot.fetch_channel(config.REMINDER_CHANNEL_ID)
                await channel.send(f"🔔 <@{user_id}> {message}")
            except Exception as e:
                logger.exception(f"Error sending reminder to channel: {e}")
        except Exception as e:
            logger.exception(f"Error sending reminder: {e}")

async def setup(bot):
    await bot.add_cog(Utilities(bot))
