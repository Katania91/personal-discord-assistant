import discord
from discord import app_commands
from discord.ext import commands
import datetime
import logging
from utils import storage, config, security

logger = logging.getLogger("discordbot")

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._message_id_cache = None

    @app_commands.command(name="update-commands", description="Force update of command list message")
    async def update_commands(self, interaction: discord.Interaction):
        if not await security.ensure_owner(interaction): return
        try:
            await self.update_command_list(force_update=True)
            await interaction.response.send_message("✅ Command list updated.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash update commands: {e}")
            await interaction.response.send_message("❌ Error updating command list.", ephemeral=True)

    @app_commands.command(name="sync-commands", description="Force sync commands with Discord")
    async def sync_commands(self, interaction: discord.Interaction):
        if not await security.ensure_owner(interaction): return
        try:
            await interaction.response.defer(ephemeral=True)
            await self.bot.tree.sync()
            await interaction.followup.send("✅ Commands synced globally. It may take a few minutes to appear.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error sync commands: {e}")
            await interaction.followup.send(f"❌ Error syncing: {e}", ephemeral=True)

    @app_commands.command(name="backup", description="Create backup of todo or agenda file")
    async def backup(self, interaction: discord.Interaction, target: str):
        if not await security.ensure_owner(interaction): return
        if target not in ("todo", "agenda"):
            await interaction.response.send_message("Use `todo` or `agenda` as target.", ephemeral=True)
            return
        try:
            await interaction.response.defer(ephemeral=True)
            file_path = config.TODO_FILE if target == 'todo' else config.AGENDA_FILE
            bak = storage.create_backup_file(file_path)
            await interaction.followup.send(f"✅ Backup created: `{storage.os.path.basename(bak)}`", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash backup: {e}")
            await interaction.followup.send("❌ Error creating backup.", ephemeral=True)

    @app_commands.command(name="list-backups", description="List available backups for todo or agenda")
    async def list_backups(self, interaction: discord.Interaction, target: str):
        if not await security.ensure_owner(interaction): return
        if target not in ("todo", "agenda"):
            await interaction.response.send_message("Use `todo` or `agenda` as target.", ephemeral=True)
            return
        try:
            file_path = config.TODO_FILE if target == 'todo' else config.AGENDA_FILE
            items = storage.list_backups(file_path)
            if not items:
                await interaction.response.send_message("No backups found.", ephemeral=True)
                return
            text = "\n".join(items[:50])
            await interaction.response.send_message(f"Available backups:\n{text}", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash list-backups: {e}")
            await interaction.response.send_message("❌ Error retrieving backup list.", ephemeral=True)

    @app_commands.command(name="restore-backup", description="Restore a backup (use exact filename) for todo or agenda")
    async def restore_backup(self, interaction: discord.Interaction, target: str, backup_filename: str):
        if not await security.ensure_owner(interaction): return
        if target not in ("todo", "agenda"):
            await interaction.response.send_message("Use `todo` or `agenda` as target.", ephemeral=True)
            return
        try:
            await interaction.response.defer(ephemeral=True)
            file_path = config.TODO_FILE if target == 'todo' else config.AGENDA_FILE
            storage.restore_backup(file_path, backup_filename)
            await interaction.followup.send(f"✅ Restored backup `{backup_filename}` for {target}.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash restore-backup: {e}")
            await interaction.followup.send("❌ Error restoring backup.", ephemeral=True)

    @app_commands.command(name="clear-all", description="(OWNER) Clear all TODO or AGENDA")
    async def clear_all(self, interaction: discord.Interaction, target: str):
        if not await security.ensure_owner(interaction): return
        if target not in ('todo', 'agenda'):
            await interaction.response.send_message("Invalid target. Use: todo or agenda.", ephemeral=True)
            return
        try:
            if target == 'todo':
                if storage.os.path.exists(config.TODO_FILE):
                    storage.create_backup_file(config.TODO_FILE)
                    storage.os.remove(config.TODO_FILE)
                await interaction.response.send_message("✅ All To-Dos removed (backup created).", ephemeral=True)
            else:
                if storage.os.path.exists(config.AGENDA_FILE):
                    storage.create_backup_file(config.AGENDA_FILE)
                    storage.os.remove(config.AGENDA_FILE)
                await interaction.response.send_message("✅ All agenda events removed (backup created).", ephemeral=True)
                # Update command list if needed
                try:
                    if self.bot.is_ready():
                        self.bot.loop.create_task(self.update_command_list())
                except Exception:
                    pass
        except Exception as e:
            logger.exception(f"Error slash clear-all: {e}")
            await interaction.response.send_message("❌ Error during operation.", ephemeral=True)

    @app_commands.command(name="stats", description="Show simple stats for To-Do and Agenda")
    async def stats(self, interaction: discord.Interaction):
        if not await security.ensure_owner(interaction): return
        try:
            todos = storage.load_todo()
            events = storage.load_events()
            total = len(todos)
            done = len([t for t in todos if t.get('done')])
            pending = total - done
            upcoming_events = len([e for e in events if e['datetime_evento'] >= datetime.datetime.now()])
            
            embed = discord.Embed(title="📊 Bot Stats", color=discord.Color.blurple(), timestamp=datetime.datetime.now())
            embed.add_field(name="To-Do: total", value=str(total), inline=True)
            embed.add_field(name="To-Do: completed", value=str(done), inline=True)
            embed.add_field(name="To-Do: pending", value=str(pending), inline=True)
            embed.add_field(name="Upcoming events", value=str(upcoming_events), inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash stats: {e}")
            await interaction.response.send_message("❌ Error calculating stats.", ephemeral=True)

    # --- HELPERS ---

    def create_commands_embed(self):
        embed = discord.Embed(
            title="🤖 Personal Bot Commands",
            description="Here are all available commands:",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        # Agenda
        embed.add_field(
            name="📅 AGENDA",
            value=(
                "`/agenda-add DD-MM-YYYY HH:MM Text` - Add event\n"
                "`/agenda-delete <id>` - Remove event\n"
                "`/today` - Show today's events\n"
                "`/tomorrow` - Show tomorrow's events\n"
                "`/week` - Show next 7 days events\n"
                "`/month` - Show current month events\n"
                "`/all` - Show ALL agenda events"
            ),
            inline=False
        )
        # Reminder
        embed.add_field(
        name="⏰ REMINDER",
        value="`/remindme <time> <message>` - Quick reminder (e.g. 10m, 2h)",
            inline=False
        )
        # Remote
        embed.add_field(
            name="🖥️ REMOTE (Windows)",
            value=(
                "`/shutdown` - Shutdown PC\n"
                "`/disconnect` - Disconnect current user\n"
                "`/lock` - Lock screen"
            ),
            inline=False
        )
        # Utility
        embed.add_field(
            name="🛠️ UTILITY",
            value=(
                "`/weather <city[, country]>` - Detailed weather\n"
                "`/password <length> <phrase:bool> <nospecial:bool>` - Generate password\n"
                "`/qr <text>` - Generate QR code\n"
                "`/shorten <url>` - Shorten URL (is.gd)\n"
                "`/screenshot` - Capture PC screenshot\n"
                "`/status-pc` - Show PC hardware/software status"
            ),
            inline=False
        )
        # Notes
        embed.add_field(
            name="📝 NOTES",
            value=(
                "• Midnight notification with daily summary\n"
                "• Persistent reminder every 15 min starting 2h before event\n"
                "• Press ✅ on persistent reminder to stop it\n"
                "• Date format: DD-MM-YYYY HH:MM (e.g. 25-12-2025 13:00)\n"
                "• Reminder: 10s (seconds), 10m (minutes), 2h (hours), 1d (days)"
            ),
            inline=False
        )
        # To-Do
        embed.add_field(
            name="✅ TO-DO",
            value=(
                "`/todo-add <text>` - Add task\n"
                "`/todo-list` - Show tasks\n"
                "`/todo-view <id|#>` - Show task with interactive buttons\n"
                "`/todo-done <id|#>` - Mark as done\n"
                "`/todo-remove <id|#>` - Remove task\n"
                "`/todo-export` - Export todo.json"
            ),
            inline=False
        )
        # Admin
        embed.add_field(
            name="🔧 ADMIN",
            value=(
                "`/update-commands` - Force update of command list message"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Bot updated • Last start: {datetime.datetime.now().strftime('%d/%m/%Y at %H:%M')}")
        return embed

    async def update_command_list(self, force_update=False):
        try:
            if not config.COMMANDS_CHANNEL_ID:
                return
            channel = await self.bot.fetch_channel(config.COMMANDS_CHANNEL_ID)
            embed = self.create_commands_embed()
            
            # Simple in-memory cache for this session
            message_id = self._message_id_cache

            if message_id and not force_update:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.edit(embed=embed)
                    logger.info("Command list updated in existing message.")
                    return
                except discord.NotFound:
                    logger.info("Previous message not found, searching history...")
                except Exception as e:
                    logger.exception(f"Error updating message: {e}")

            async for msg in channel.history(limit=50):
                if msg.author == self.bot.user and msg.embeds:
                    if "Personal Bot Commands" in (msg.embeds[0].title or ""):
                        await msg.edit(embed=embed)
                        self._message_id_cache = msg.id
                        logger.info("Found existing message and updated.")
                        return

            message = await channel.send(embed=embed)
            self._message_id_cache = message.id
            logger.info("New command list sent.")

        except Exception as e:
            logger.exception(f"Error updating command list: {e}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
