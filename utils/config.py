import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---

# Data directory configuration
DEFAULT_DATA_DIR = os.path.join(Path.home(), "Documents", "DiscordBot")
DATA_DIR = os.getenv("BOT_DATA_DIR", DEFAULT_DATA_DIR)
os.makedirs(DATA_DIR, exist_ok=True)

# Logging setup
logger = logging.getLogger("discordbot")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(os.path.join(DATA_DIR, "bot.log"), encoding='utf-8')
    ch = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)

# Bot Token
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

def get_int_env(name, default):
    val = os.getenv(name)
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(str(val).strip())
    except Exception:
        logger.warning(f"Invalid variable {name}: '{val}'. Using default {default}.")
        return default

# IDs configuration
OWNER_ID = get_int_env("OWNER_ID", 0)
REMINDER_CHANNEL_ID = get_int_env("REMINDER_CHANNEL_ID", 0)
COMMANDS_CHANNEL_ID = get_int_env("COMMANDS_CHANNEL_ID", 0)

# File paths
AGENDA_FILE = os.path.join(DATA_DIR, "agenda.json")
TODO_FILE = os.path.join(DATA_DIR, "todo.json")
SECRET_2FA_FILE = os.path.join(DATA_DIR, "secret_2fa.json")
