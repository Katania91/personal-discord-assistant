import discord
import pyotp
import asyncio
import ctypes
import platform
from utils import config, storage

def request_physical_confirmation(message: str, title: str = "Bot Security Confirmation") -> bool:
    """
    Shows a modal popup on the host PC. Blocks execution until Yes or No is pressed.
    Returns True if user presses 'Yes'.
    """
    if platform.system() != "Windows":
        return True  # On Linux/Mac we assume True or handle differently
    
    # MB_YESNO=0x04, MB_ICONWARNING=0x30, MB_SYSTEMMODAL=0x1000 (topmost)
    # IDYES=6
    MB_YESNO = 0x04
    MB_ICONWARNING = 0x30
    MB_SYSTEMMODAL = 0x1000
    
    ret = ctypes.windll.user32.MessageBoxW(0, message, title, MB_YESNO | MB_ICONWARNING | MB_SYSTEMMODAL)
    return ret == 6

async def check_security(interaction: discord.Interaction, otp: str, action_name: str) -> bool:
    """
    Handles hybrid security:
    - If OTP is provided: verify 2FA (Remote Mode)
    - If OTP is not provided: physical popup (Local Mode)
    """
    if otp:
        secret = storage.load_secret_2fa()
        if not secret:
            await interaction.followup.send("❌ 2FA not configured. Run `/setup-2fa` from PC before using remote commands.", ephemeral=True)
            return False
        
        totp = pyotp.TOTP(secret)
        if totp.verify(otp):
            return True
        else:
            await interaction.followup.send("⛔ Invalid or expired 2FA code.", ephemeral=True)
            return False
    else:
        # Fallback to physical confirmation
        msg = f"Command execution requested: {action_name}\nIs that you? Click YES to confirm."
        confirmed = await asyncio.to_thread(request_physical_confirmation, msg, f"Bot Security: {action_name}")
        if not confirmed:
            await interaction.followup.send("⛔ Action denied physically from host PC.", ephemeral=True)
            return False
        return True

async def ensure_owner(interaction: discord.Interaction) -> bool:
    """Verifies that the user is the owner; sends message if unauthorized."""
    if interaction.user.id != config.OWNER_ID:
        try:
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
        except Exception:
            pass
        return False
    return True
