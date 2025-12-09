import discord
from discord import app_commands
from discord.ext import commands
import datetime
import uuid
import logging
from utils import storage, config, security

logger = logging.getLogger("discordbot")

class ToDo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="todo-add", description="Add a task to To-Do list")
    async def todo_add(self, interaction: discord.Interaction, text: str):
        if not await security.ensure_owner(interaction): return
        await interaction.response.defer(ephemeral=True)
        try:
            items = storage.load_todo()
            new_item = {
                'id': str(uuid.uuid4()),
                'user_id': interaction.user.id,
                'text': text,
                'created': datetime.datetime.now().isoformat(),
                'done': False
            }
            items.append(new_item)
            if storage.save_todo(items):
                await interaction.followup.send(f"✅ Task added: **{text}** (ID: `{new_item['id']}`)")
            else:
                await interaction.followup.send("❌ Error saving.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash todo add: {e}")
            await interaction.followup.send("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="todo-list", description="Show your To-Do list")
    async def todo_list(self, interaction: discord.Interaction):
        if not await security.ensure_owner(interaction): return
        try:
            items = [i for i in storage.load_todo() if i['user_id'] == interaction.user.id]
            if not items:
                await interaction.response.send_message("✨ No tasks in your To-Do list.", ephemeral=True)
                return
            lines = []
            for idx, it in enumerate(items, start=1):
                if it.get('done'):
                    txt = f"~~{it['text']}~~"
                    status = "✅"
                else:
                    txt = it['text']
                    status = "🔲"
                lines.append(f"{idx}. {status} {txt} (`{it['id'][:8]}`)")
            embed = discord.Embed(title="📝 To-Do List", description="\n".join(lines), color=discord.Color.blurple())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash todo list: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="todo-view", description="View a specific task")
    async def todo_view(self, interaction: discord.Interaction, id_or_index: str):
        if not await security.ensure_owner(interaction): return
        try:
            items = storage.load_todo()
            item = self.find_todo(items, id_or_index, interaction.user.id)
            if not item:
                await interaction.response.send_message("❌ Task not found.", ephemeral=True)
                return
            status = "✅ Completed" if item.get('done') else "🔲 Not completed"
            embed = discord.Embed(title=f"📝 Task: {item['text']}", color=discord.Color.blue())
            embed.add_field(name="ID", value=item['id'], inline=False)
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Created", value=item.get('created', 'N/A'), inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash todo view: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="todo-done", description="Mark a task as completed")
    async def todo_done(self, interaction: discord.Interaction, id_or_index: str):
        if not await security.ensure_owner(interaction): return
        try:
            items = storage.load_todo()
            target = self.find_todo(items, id_or_index, interaction.user.id)
            if not target:
                await interaction.response.send_message("❌ Task not found.", ephemeral=True)
                return
            for it in items:
                if it['id'] == target['id']:
                    it['done'] = True
                    it['done_at'] = datetime.datetime.now().isoformat()
            storage.save_todo(items)
            await interaction.response.send_message(f"✅ Task marked as done: **{target['text']}**", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash todo done: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="todo-remove", description="Remove a task")
    async def todo_remove(self, interaction: discord.Interaction, id_or_index: str):
        if not await security.ensure_owner(interaction): return
        try:
            items = storage.load_todo()
            target = self.find_todo(items, id_or_index, interaction.user.id)
            if not target:
                await interaction.response.send_message("❌ Task not found.", ephemeral=True)
                return
            items = [i for i in items if i['id'] != target['id']]
            storage.save_todo(items)
            await interaction.response.send_message(f"🗑️ Task removed: **{target['text']}**", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash todo remove: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="todo-export", description="Export todo.json file")
    async def todo_export(self, interaction: discord.Interaction):
        if not await security.ensure_owner(interaction): return
        try:
            if not storage.os.path.exists(config.TODO_FILE):
                await interaction.response.send_message("No todo file to export.", ephemeral=True)
                return
            await interaction.response.send_message(file=discord.File(config.TODO_FILE), ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash todo export: {e}")
            await interaction.response.send_message("❌ Error during export.", ephemeral=True)

    @app_commands.command(name="export-todo", description="Export To-Do list as CSV")
    async def export_todo_csv(self, interaction: discord.Interaction):
        if not await security.ensure_owner(interaction): return
        try:
            await interaction.response.defer(ephemeral=True)
            items = storage.load_todo()
            csv_bytes = storage.todo_to_csv(items)
            bio = storage.io.BytesIO(csv_bytes)
            bio.seek(0)
            await interaction.followup.send(file=discord.File(bio, filename="todo_export.csv"), ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash export-todo: {e}")
            await interaction.response.send_message("❌ Error exporting.", ephemeral=True)

    @app_commands.command(name="search-todo", description="Search in your To-Do list (substring match)")
    async def search_todo(self, interaction: discord.Interaction, query: str):
        if not await security.ensure_owner(interaction): return
        try:
            items = [i for i in storage.load_todo() if i.get('user_id') == interaction.user.id]
            matches = [i for i in items if query.lower() in i.get('text', '').lower()]
            if not matches:
                await interaction.response.send_message("No results.", ephemeral=True)
                return
            lines = []
            for idx, it in enumerate(matches, start=1):
                status = "✅" if it.get('done') else "🔲"
                pr = it.get('priority', 'normal')
                tags = ','.join(it.get('tags', [])) if it.get('tags') else ''
                lines.append(f"{idx}. {status} {it.get('text')} (`{it['id'][:8]}`) [prio:{pr}]{(' ['+tags+']') if tags else ''}")
            embed = discord.Embed(title=f"🔎 Results for: {query}", description="\n".join(lines), color=discord.Color.blurple())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash search-todo: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="clear-completed", description="Remove completed tasks from To-Do list")
    async def clear_completed(self, interaction: discord.Interaction):
        if not await security.ensure_owner(interaction): return
        try:
            items = storage.load_todo()
            before = len(items)
            items = [i for i in items if not (i.get('user_id') == interaction.user.id and i.get('done'))]
            removed = before - len(items)
            if storage.save_todo(items):
                await interaction.response.send_message(f"🧹 Removed {removed} completed tasks.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Error saving.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash clear-completed: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="set-priority", description="Set priority for a task (low, normal, high, urgent)")
    async def set_priority(self, interaction: discord.Interaction, id_or_index: str, level: str):
        if not await security.ensure_owner(interaction): return
        level = level.lower()
        if level not in ('low', 'normal', 'high', 'urgent'):
            await interaction.response.send_message("Invalid priority. Use: low, normal, high, urgent.", ephemeral=True)
            return
        try:
            items = storage.load_todo()
            target = self.find_todo(items, id_or_index, interaction.user.id)
            if not target:
                await interaction.response.send_message("Task not found.", ephemeral=True)
                return
            for it in items:
                if it['id'] == target['id']:
                    it['priority'] = level
            storage.save_todo(items)
            await interaction.response.send_message(f"✅ Priority set to {level} for: **{target['text']}**", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash set-priority: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    @app_commands.command(name="tag-todo", description="Add or remove a tag from a task")
    async def tag_todo(self, interaction: discord.Interaction, id_or_index: str, action: str, tag: str):
        if not await security.ensure_owner(interaction): return
        action = action.lower()
        if action not in ('add', 'remove'):
            await interaction.response.send_message("Invalid action. Use add or remove.", ephemeral=True)
            return
        try:
            items = storage.load_todo()
            target = self.find_todo(items, id_or_index, interaction.user.id)
            if not target:
                await interaction.response.send_message("Task not found.", ephemeral=True)
                return
            for it in items:
                if it['id'] == target['id']:
                    tags = set(it.get('tags', []))
                    if action == 'add':
                        tags.add(tag)
                    else:
                        tags.discard(tag)
                    it['tags'] = list(tags)
            storage.save_todo(items)
            await interaction.response.send_message(f"✅ Tag {action} executed on: **{target['text']}**", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash tag-todo: {e}")
            await interaction.response.send_message("❌ Unexpected error.", ephemeral=True)

    def find_todo(self, items, id_or_index, user_id):
        user_items = [i for i in items if i.get('user_id') == user_id]
        if id_or_index.isdigit():
            idx = int(id_or_index) - 1
            if 0 <= idx < len(user_items):
                return user_items[idx]
            return None
        # id prefix
        for it in user_items:
            if it.get('id', '').startswith(id_or_index):
                return it
        return None

async def setup(bot):
    await bot.add_cog(ToDo(bot))
