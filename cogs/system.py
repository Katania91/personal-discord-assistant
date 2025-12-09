import discord
from discord import app_commands
from discord.ext import commands
import platform
import asyncio
import io
import datetime
import pyotp
import logging
from utils import security, common, storage, config

logger = logging.getLogger("discordbot")

class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shutdown", description="Shutdown PC (Windows only)")
    async def shutdown(self, interaction: discord.Interaction, otp: str = None):
        if not await security.ensure_owner(interaction): return
        if platform.system() != "Windows":
            await interaction.response.send_message("❌ This command is available only on Windows.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        if not await security.check_security(interaction, otp, "PC SHUTDOWN"):
            return

        try:
            await interaction.followup.send("🖥️ Shutting down PC...", ephemeral=True)
            await asyncio.sleep(1)
            await common.run_system_command("shutdown /s /t 0")
        except Exception as e:
            logger.exception(f"Error slash shutdown: {e}")
            await interaction.followup.send("❌ Error during shutdown.", ephemeral=True)

    @app_commands.command(name="disconnect", description="Disconnect current user (Windows only)")
    async def disconnect(self, interaction: discord.Interaction, otp: str = None):
        if not await security.ensure_owner(interaction): return
        if platform.system() != "Windows":
            await interaction.response.send_message("❌ This command is available only on Windows.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        if not await security.check_security(interaction, otp, "USER DISCONNECT"):
            return

        try:
            await interaction.followup.send("🔒 Disconnecting current user...", ephemeral=True)
            await asyncio.sleep(1)
            await common.run_system_command("shutdown /l")
        except Exception as e:
            logger.exception(f"Error slash disconnect: {e}")
            await interaction.followup.send("❌ Error during disconnect.", ephemeral=True)

    @app_commands.command(name="lock", description="Lock screen (Windows only)")
    async def lock(self, interaction: discord.Interaction, otp: str = None):
        if not await security.ensure_owner(interaction): return
        if platform.system() != "Windows":
            await interaction.response.send_message("❌ This command is available only on Windows.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        if not await security.check_security(interaction, otp, "SCREEN LOCK"):
            return

        try:
            await interaction.followup.send("🔐 Locking screen...", ephemeral=True)
            await asyncio.sleep(1)
            await common.run_system_command("rundll32.exe user32.dll,LockWorkStation")
        except Exception as e:
            logger.exception(f"Error slash lock: {e}")
            await interaction.followup.send("❌ Error during screen lock.", ephemeral=True)

    @app_commands.command(name="screenshot", description="Capture remote PC screenshot (owner only)")
    async def screenshot(self, interaction: discord.Interaction, otp: str = None):
        if not await security.ensure_owner(interaction): return
        if platform.system() != "Windows":
            await interaction.response.send_message("❌ Screenshot available only on Windows.", ephemeral=True)
            return
        try:
            import mss
        except ImportError:
            await interaction.response.send_message("❌ 'mss' module not installed. Run `pip install mss`.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        if not await security.check_security(interaction, otp, "DESKTOP SCREENSHOT"):
            return

        try:
            data = await asyncio.to_thread(common._capture_screenshot_bytes_sync)
            file_obj = discord.File(io.BytesIO(data), filename="screenshot.png")
            embed = discord.Embed(title="📸 Screenshot Ready", color=discord.Color.dark_teal(), timestamp=datetime.datetime.now())
            embed.set_image(url="attachment://screenshot.png")
            embed.set_footer(text="Captured from local PC")
            await interaction.followup.send(embed=embed, file=file_obj, ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash screenshot: {e}")
            await interaction.followup.send("❌ Could not capture screenshot.", ephemeral=True)

    @app_commands.command(name="status-pc", description="Show host PC status")
    async def status_pc(self, interaction: discord.Interaction):
        if not await security.ensure_owner(interaction): return
        await interaction.response.defer(ephemeral=True)
        try:
            info = await asyncio.to_thread(common._collect_system_status_sync)
            embed = discord.Embed(title="🖥️ PC Status", color=discord.Color.dark_blue(), timestamp=datetime.datetime.now())
            embed.add_field(name="System", value=f"{info['hostname']}\n{info['platform']}\nPython {info['python']}", inline=False)
            if info['uptime']:
                days = info['uptime'].days
                hours, rem = divmod(info['uptime'].seconds, 3600)
                minutes = rem // 60
                embed.add_field(name="Uptime", value=f"{days}d {hours}h {minutes}m", inline=True)
            if info['cpu_percent'] is not None:
                embed.add_field(name="CPU", value=f"{info['cpu_percent']:.1f}%", inline=True)
            if info['memory']:
                mem = info['memory']
                embed.add_field(name="RAM", value=f"{common.format_bytes(mem['used'])}/{common.format_bytes(mem['total'])} ({mem['percent']}%)", inline=True)
            if info['disk']:
                disk = info['disk']
                embed.add_field(name="Main Disk", value=f"{common.format_bytes(disk['used'])}/{common.format_bytes(disk['total'])}\nFree: {common.format_bytes(disk['free'])}", inline=False)
            if info['processes'] is not None:
                embed.add_field(name="Processes", value=str(info['processes']), inline=True)
            if not info['psutil_available']:
                embed.add_field(name="Note", value="Install `psutil` for advanced metrics (`pip install psutil`).", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception(f"Error slash status-pc: {e}")
            await interaction.followup.send("❌ Cannot retrieve PC status.", ephemeral=True)

    @app_commands.command(name="setup-2fa", description="Configure 2FA for remote commands")
    async def setup_2fa(self, interaction: discord.Interaction):
        if not await security.ensure_owner(interaction): return
        
        await interaction.response.defer(ephemeral=True)
        
        # Generate new secret
        secret = pyotp.random_base32()
        
        # Save
        if not storage.save_secret_2fa(secret):
            await interaction.followup.send("❌ Error saving configuration.", ephemeral=True)
            return

        # Generate URI for QR code
        uri = pyotp.totp.TOTP(secret).provisioning_uri(name=interaction.user.name, issuer_name="DiscordBot")
        
        # Generate QR code image
        qr_bytes = await common.generate_qr_code(uri)
        
        if qr_bytes:
            file_qr = discord.File(io.BytesIO(qr_bytes), filename="qrcode.png")
            embed = discord.Embed(
                title="🔐 2FA Configuration",
                description=f"Scan this QR code with Google Authenticator or Authy.\n\n**Manual Secret:** `{secret}`\n\nOnce configured, use remote commands by adding the code (e.g. `/shutdown otp:123456`).",
                color=discord.Color.gold()
            )
            embed.set_image(url="attachment://qrcode.png")
            await interaction.followup.send(embed=embed, file=file_qr, ephemeral=True)
        else:
            await interaction.followup.send(f"✅ 2FA Configured.\n**Secret:** `{secret}`\n(Could not generate QR code, enter secret manually)", ephemeral=True)

    @app_commands.command(name="test-security", description="Test physical confirmation system (popup)")
    async def test_security(self, interaction: discord.Interaction):
        if not await security.ensure_owner(interaction): return
        
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("🔔 Opening popup on host PC. Check the screen!", ephemeral=True)
        
        confirmed = await asyncio.to_thread(security.request_physical_confirmation, "This is a SECURITY TEST.\nIf you see this, the system works.\n\nClick YES to confirm, NO to deny.", "Bot Security Test")
        
        if confirmed:
            await interaction.followup.send("✅ Test passed! You clicked YES on PC.", ephemeral=True)
        else:
            await interaction.followup.send("⛔ Test passed! You clicked NO (or closed window).", ephemeral=True)

async def setup(bot):
    await bot.add_cog(System(bot))
