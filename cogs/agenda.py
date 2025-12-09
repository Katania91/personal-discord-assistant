import discord
from discord import app_commands
from discord.ext import commands
import datetime
from datetime import timedelta
import asyncio
import logging
from utils import storage, config

logger = logging.getLogger("discordbot")

class Agenda(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_reminders = {}      # event_id -> task
        self.ack_events = {}            # event_id -> asyncio.Event
        self.message_to_event = {}      # message_id -> event_id

    async def cog_load(self):
        self.bot.loop.create_task(self.schedule_event_reminders_on_startup())

    # --- COMMANDS ---

    @app_commands.command(name="agenda-add", description="Add event to agenda (DD-MM-YYYY HH:MM)")
    async def agenda_add(self, interaction: discord.Interaction, date: str, time_str: str, event: str):
        if not await self._ensure_owner(interaction): return
        try:
            datetime_obj = datetime.datetime.strptime(f"{date} {time_str}", "%d-%m-%Y %H:%M")
            if datetime_obj < datetime.datetime.now():
                await interaction.response.send_message("❌ Cannot add event in the past.", ephemeral=True)
                return
            events = storage.load_events()
            import uuid
            new_event = {"id": str(uuid.uuid4()), "user_id": interaction.user.id, "datetime_evento": datetime_obj, "evento": event}
            events.append(new_event)
            if storage.save_events(events):
                await interaction.response.send_message(f"✅ Event saved: `{event}` on {date} at {time_str}", ephemeral=True)
                # Schedule reminder if needed
                self.schedule_new_event_reminder(new_event)
            else:
                await interaction.response.send_message("❌ Error saving to file.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash agenda add: {e}")
            await interaction.response.send_message("❌ Format error or unexpected error.", ephemeral=True)

    @app_commands.command(name="agenda-delete", description="Remove event from agenda by ID")
    async def agenda_delete(self, interaction: discord.Interaction, event_id: str):
        if not await self._ensure_owner(interaction): return
        try:
            events = storage.load_events()
            new_events = [e for e in events if e['id'] != event_id]
            if len(new_events) == len(events):
                await interaction.response.send_message("❌ Event not found.", ephemeral=True)
                return
            if storage.save_events(new_events):
                await interaction.response.send_message(f"🗑️ Event {event_id} removed.", ephemeral=True)
                # Cancel reminder if active
                if event_id in self.active_reminders:
                    self.active_reminders[event_id].cancel()
                    self.active_reminders.pop(event_id, None)
                    self.ack_events.pop(event_id, None)
            else:
                await interaction.response.send_message("❌ Error during removal.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash agenda delete: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="today", description="Show today's events")
    async def today(self, interaction: discord.Interaction):
        if not await self._ensure_owner(interaction): return
        try:
            events = [e for e in storage.load_events() if e['datetime_evento'].date() == datetime.datetime.now().date() and e['user_id'] == config.OWNER_ID]
            await interaction.response.send_message(embed=self.create_events_embed(events, "🗓️ Today's Schedule"), ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash today: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="tomorrow", description="Show tomorrow's events")
    async def tomorrow(self, interaction: discord.Interaction):
        if not await self._ensure_owner(interaction): return
        try:
            tomorrow_date = (datetime.datetime.now() + timedelta(days=1)).date()
            events = [e for e in storage.load_events() if e['datetime_evento'].date() == tomorrow_date and e['user_id'] == config.OWNER_ID]
            await interaction.response.send_message(embed=self.create_events_embed(events, "📅 Tomorrow's Schedule", discord.Color.green()), ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash tomorrow: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="week", description="Show next 7 days events")
    async def week(self, interaction: discord.Interaction):
        if not await self._ensure_owner(interaction): return
        try:
            today_date = datetime.datetime.now().date()
            end_week = (datetime.datetime.now() + timedelta(days=7)).date()
            events = [e for e in storage.load_events() if today_date <= e['datetime_evento'].date() < end_week and e['user_id'] == config.OWNER_ID]
            events.sort(key=lambda x: x['datetime_evento'])
            await interaction.response.send_message(embed=self.create_events_embed(events, "📆 Next 7 Days Schedule", discord.Color.orange()), ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash week: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="month", description="Show current month events")
    async def month(self, interaction: discord.Interaction):
        if not await self._ensure_owner(interaction): return
        try:
            now = datetime.datetime.now()
            events = [e for e in storage.load_events() if e['datetime_evento'].year == now.year and e['datetime_evento'].month == now.month and e['user_id'] == config.OWNER_ID]
            events.sort(key=lambda x: x['datetime_evento'])
            await interaction.response.send_message(embed=self.create_events_embed(events, "🗓️ Current Month Schedule", discord.Color.purple()), ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash month: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="all", description="Show all agenda events")
    async def all_events(self, interaction: discord.Interaction):
        if not await self._ensure_owner(interaction): return
        try:
            events = [e for e in storage.load_events() if e['user_id'] == config.OWNER_ID]
            events.sort(key=lambda x: x['datetime_evento'])
            await interaction.response.send_message(embed=self.create_events_embed(events, f"📋 Full Agenda - {len(events)} Events", discord.Color.gold()), ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash all: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    # --- HELPERS ---

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != config.OWNER_ID:
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return False
        return True

    def create_events_embed(self, events, title, color=discord.Color.blue()):
        embed = discord.Embed(title=title, color=color, timestamp=datetime.datetime.now())
        if not events:
            embed.add_field(name="✨ No events", value="No events scheduled.", inline=False)
            return embed

        events_by_date = {}
        for event in events:
            date = event['datetime_evento'].date()
            if date not in events_by_date:
                events_by_date[date] = []
            events_by_date[date].append((event['datetime_evento'].time(), event['evento']))

        for date in sorted(events_by_date.keys()):
            date_obj = datetime.datetime.strptime(str(date), "%Y-%m-%d")
            date_formatted = date_obj.strftime("%d/%m/%Y")
            weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            weekday = weekdays[date_obj.weekday()]
            events_list = "\n".join([f"• `{t.strftime('%H:%M')}` - {e}" for t, e in sorted(events_by_date[date], key=lambda x: x[0])])
            embed.add_field(
                name=f"📅 {weekday} {date_formatted}",
                value=events_list,
                inline=False
            )
        return embed

    # --- REMINDER LOGIC ---

    async def start_event_reminder_task(self, event):
        """Starts the persistent cycle from T-2h until ack (or event start)."""
        event_id = event['id']
        if event_id in self.active_reminders:
            return
        self.ack_events[event_id] = asyncio.Event()
        task = asyncio.create_task(self.remind_until_ack(event))
        self.active_reminders[event_id] = task
        logger.info(f"Persistent reminder task activated for '{event['evento']}'")

    async def remind_until_ack(self, event):
        """Sends reminder every 15 minutes until reaction ✅ or event time."""
        event_id = event['id']
        event_dt = event['datetime_evento']

        try:
            while datetime.datetime.now() < event_dt and not self.ack_events[event_id].is_set():
                try:
                    user = await self.bot.fetch_user(config.OWNER_ID)
                    channel = await self.bot.fetch_channel(config.REMINDER_CHANNEL_ID)
                except Exception as e:
                    logger.exception(f"Error fetch user/channel: {e}")
                    try:
                        await asyncio.wait_for(self.ack_events[event_id].wait(), timeout=15 * 60)
                    except asyncio.TimeoutError:
                        continue
                    else:
                        break

                time_remaining = event_dt - datetime.datetime.now()
                hours, rem = divmod(int(time_remaining.total_seconds()), 3600)
                minutes, _ = divmod(rem, 60)

                embed = discord.Embed(
                    title="🚨 URGENT REMINDER 🚨",
                    description=f"Event **{event['evento']}** is at **{event_dt.strftime('%H:%M')}**.",
                    color=discord.Color.red()
                )
                embed.add_field(name="⏳ Time remaining", value=f"{hours} hours and {minutes} minutes")
                embed.set_footer(text="Press ✅ to stop notifications.")

                try:
                    msg_private = await user.send(embed=embed)
                    msg_channel = await channel.send(content=f"<@{config.OWNER_ID}>", embed=embed)
                    await msg_private.add_reaction("✅")
                    await msg_channel.add_reaction("✅")
                    self.message_to_event[msg_private.id] = event_id
                    self.message_to_event[msg_channel.id] = event_id
                except Exception as e:
                    logger.exception(f"Error sending reminder: {e}")

                try:
                    await asyncio.wait_for(self.ack_events[event_id].wait(), timeout=15 * 60)
                except asyncio.TimeoutError:
                    continue
                else:
                    break
        finally:
            self.ack_events.pop(event_id, None)
            self.active_reminders.pop(event_id, None)
            to_del = [mid for mid, eid in self.message_to_event.items() if eid == event_id]
            for mid in to_del:
                self.message_to_event.pop(mid, None)

    async def schedule_event_reminders_on_startup(self):
        await self.bot.wait_until_ready()
        logger.info("Scheduling event reminders on startup...")
        now = datetime.datetime.now()
        for event in storage.load_events():
            self.schedule_new_event_reminder(event)

    def schedule_new_event_reminder(self, event):
        now = datetime.datetime.now()
        event_dt = event['datetime_evento']
        if now >= event_dt:
            return
        reminder_start_time = event_dt - timedelta(hours=2)
        if now >= reminder_start_time:
            self.bot.loop.create_task(self.start_event_reminder_task(event))
        else:
            self.bot.scheduler.add_job(
                self.start_event_reminder_task, 'date',
                run_date=reminder_start_time,
                args=[event],
                id=f"start_nag_{event['id']}",
                misfire_grace_time=3600,
                replace_existing=True
            )

    async def daily_reminder(self):
        logger.info(f"Running daily midnight reminder check...")
        today_date = datetime.datetime.now().date()
        events = storage.load_events()
        todays_events = [e for e in events if e['datetime_evento'].date() == today_date and e['user_id'] == config.OWNER_ID]
        if not todays_events:
            logger.info("No events for today.")
            return

        message = "🔔 **DAILY SUMMARY!** Here is your schedule for today:\n"
        todays_events.sort(key=lambda x: x['datetime_evento'].time())
        for event in todays_events:
            message += f"- `{event['datetime_evento'].strftime('%H:%M')}`: {event['evento']}\n"

        try:
            user = await self.bot.fetch_user(config.OWNER_ID)
            await user.send(message)
            channel = await self.bot.fetch_channel(config.REMINDER_CHANNEL_ID)
            await channel.send(message)
        except Exception as e:
            logger.exception(f"Error sending daily reminder: {e}")

    def clean_old_events(self):
        events = storage.load_events()
        threshold = datetime.datetime.now() - timedelta(days=1)
        valid_events = [e for e in events if e['datetime_evento'] >= threshold]
        removed_count = len(events) - len(valid_events)
        if removed_count > 0 and storage.save_events(valid_events):
            logger.info(f"Removed {removed_count} old events.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id != config.OWNER_ID:
            return
        if getattr(payload.emoji, "name", None) != "✅":
            return

        event_id = self.message_to_event.get(payload.message_id)
        if not event_id:
            return

        ev_flag = self.ack_events.get(event_id)
        if ev_flag and not ev_flag.is_set():
            ev_flag.set()

        try:
            channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
            await channel.send("👍 Reminder confirmed and stopped.")
            try:
                msg = await channel.fetch_message(payload.message_id)
                await msg.delete()
            except Exception:
                pass
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(Agenda(bot))
