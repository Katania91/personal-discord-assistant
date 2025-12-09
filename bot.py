import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import os
import logging
from utils import config

# Setup logging
logger = logging.getLogger("discordbot")

# --- BOT SETUP ---

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.scheduler = AsyncIOScheduler()

    async def setup_hook(self):
        # Load extensions
        initial_extensions = [
            'cogs.agenda',
            'cogs.todo',
            'cogs.system',
            'cogs.utilities',
            'cogs.admin'
        ]
        
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.exception(f"Failed to load extension {ext}: {e}")

    async def on_ready(self):
        logger.info(f'Bot connected as {self.user}')
        
        # Start scheduler
        # We need to access the methods from the cogs.
        # Since we can't easily pass instance methods to scheduler before cogs are loaded,
        # we can retrieve the cog instance and add jobs here, or let cogs add their own jobs in cog_load/on_ready.
        # The Agenda cog adds its own startup tasks.
        # We need to add the daily reminder and cleanup tasks.
        
        agenda_cog = self.get_cog('Agenda')
        if agenda_cog:
            self.scheduler.add_job(agenda_cog.daily_reminder, CronTrigger(hour=0, minute=0, second=1))
            self.scheduler.add_job(agenda_cog.clean_old_events, CronTrigger(hour=2, minute=0))
        
        self.scheduler.start()
        logger.info('Scheduler activated.')

        # Sync commands
        try:
            logger.info("Syncing Slash commands with Discord...")
            TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")
            if TEST_GUILD_ID:
                try:
                    guild_id = int(TEST_GUILD_ID)
                    logger.info(f"Syncing commands only for guild {guild_id}")
                    self.tree.clear_commands(guild=discord.Object(id=guild_id))
                    await self.tree.sync(guild=discord.Object(id=guild_id))
                except Exception:
                    logger.exception("Error syncing slash commands on specific guild")
            else:
                await self.tree.sync()
                logger.info("Slash commands synced globally.")
        except Exception:
            logger.exception("Error syncing slash commands")
        
        # Update command list
        admin_cog = self.get_cog('Admin')
        if admin_cog:
            await admin_cog.update_command_list()

    async def on_command_completion(self, ctx):
        if ctx.author.id == config.OWNER_ID:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

if __name__ == "__main__":
    if not config.BOT_TOKEN:
        raise RuntimeError("Token not configured.")
    
    bot = MyBot()
    bot.run(config.BOT_TOKEN)
