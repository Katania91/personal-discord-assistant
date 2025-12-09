# 🤖 Personal Discord Assistant

A powerful, modular, and secure Discord bot designed to be your personal assistant. It handles your agenda, to-do list, and even allows remote control of your PC (Windows) with 2FA security.

## ✨ Features

### 📅 Agenda & Scheduling
- **Event Management**: Add events with date and time (`/agenda-add`).
- **Smart Reminders**:
  - Starts notifying you **2 hours before** the event.
  - Repeats every **15 minutes** until you confirm receipt by reacting with ✅.
  - **Daily Summary**: Sends a summary of the day's events every midnight.
- **Views**: Check schedule for Today, Tomorrow, Week, Month, or All.

### ✅ To-Do List
- **Task Management**: Add, view, complete, and delete tasks.
- **Priorities & Tags**: Organize tasks with priority levels (low/normal/high/urgent) and tags.
- **Export**: Export your list to JSON or CSV.

### 🖥️ Remote PC Control (Windows Only)
Control your host machine remotely. **Protected by 2FA (OTP)**.
- **Power Control**: Shutdown (`/shutdown`), Log off (`/disconnect`), Lock Screen (`/lock`).
- **Monitoring**: Get a real-time **Screenshot** (`/screenshot`) of your desktop.
- **System Status**: View CPU, RAM, Disk usage, and Uptime (`/status-pc`).

### 🛠️ Utilities
- **Weather**: Check weather for any city (`/weather`).
- **Security**: Generate secure passwords (`/password`).
- **QR Codes**: Generate QR codes from text (`/qr`).
- **URL Shortener**: Shorten long URLs (`/shorten`).
- **Pomodoro**: Simple timer for focus sessions (`/pomodoro`).

---

## 📂 Data Storage & Configuration

By default, the bot stores all its data (logs, database JSONs, backups) in your **Documents** folder to keep the installation directory clean.

**Default Path:**
- Windows: `C:\Users\YourName\Documents\DiscordBot`

**Custom Path:**
You can change this location by setting the `BOT_DATA_DIR` variable in the `.env` file.

---

## 🚀 Installation Guide

### 1. Prerequisites
- **Python 3.10+**: [Download Here](https://www.python.org/downloads/). **Make sure to check "Add Python to PATH" during installation.**
- **Git** (Optional, to clone the repo).

### 2. Discord Developer Setup
You need to create a bot application on Discord.

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** and give it a name (e.g., "MyAssistant").
3. Go to the **Bot** tab on the left:
   - Click **Add Bot**.
   - **IMPORTANT**: Scroll down to **Privileged Gateway Intents**.
   - Enable **Message Content Intent**.
   - Enable **Server Members Intent**.
   - Enable **Presence Intent**.
   - Click **Save Changes**.
   - Click **Reset Token** to get your `DISCORD_BOT_TOKEN`. Copy it immediately.
4. Go to the **OAuth2** tab -> **URL Generator**:
   - **Scopes**: Check `bot` and `applications.commands`.
   - **Bot Permissions**: Check `Administrator` (easiest for a personal bot) or manually select permissions like `Send Messages`, `Attach Files`, `Manage Messages`.
   - Copy the **Generated URL** at the bottom and open it in your browser to invite the bot to your server.

### 3. Setup the Code
1. Download this repository.
2. Open a terminal in the bot folder.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 4. Configuration (.env)
Since `.env` files are often hidden or not uploaded to GitHub, you need to create one manually.

1. Create a new file named `.env` in the main folder.
2. Open it with a text editor (Notepad, VS Code, etc.).
3. Copy and paste the following content into it:

```ini
# Your Bot Token from Developer Portal
DISCORD_BOT_TOKEN=your_token_here

# Your Discord User ID (Right-click your name in Discord -> Copy User ID)
# *Developer Mode must be enabled in Discord Settings -> Advanced*
OWNER_ID=123456789012345678

# (Optional) Channel ID for reminders
REMINDER_CHANNEL_ID=123456789012345678

# (Optional) Channel ID for the auto-updating command list
COMMANDS_CHANNEL_ID=123456789012345678

# (Optional) Change where data is saved
# BOT_DATA_DIR=C:/MyCustomDataFolder
```

4. Replace `your_token_here` and the IDs with your actual data.
5. Save the file.

### 5. Run the Bot
```bash
python bot.py
```
If successful, you will see `Bot connected as Name#1234` in the console.

---

## 🛡️ Security System (2FA & Physical Check)

This bot implements a dual-layer security system for sensitive commands (like shutdown or screenshot) to prevent accidents or unauthorized access.

### How it works:

1. **Remote Mode (e.g., from Phone)**:
   If you are away from your PC, you must provide a **Time-based One-Time Password (OTP)**.
   - Example: `/shutdown otp:123456`
   - You get this code from an app like Google Authenticator.

2. **Local Mode (from the Host PC)**:
   If you run the command without an OTP, the bot triggers a **Physical Verification**.
   - A popup window will appear on your PC screen asking for confirmation.
   - You must click "Yes" on the PC to execute the command.
   - **Why?** This prevents accidental shutdowns if you are just testing commands or if your account is compromised but the attacker doesn't have your 2FA.

### Setup 2FA:
1. Run `/setup-2fa` in Discord.
2. Scan the QR Code with **Google Authenticator** or **Authy**.
3. You are ready to use remote commands!

---

## 🤖 Auto-Start on Windows (Background)

If you want the bot to start automatically when you turn on your PC, without opening any window:

1. Press `Win + R` on your keyboard.
2. Type `shell:startup` and press Enter. This opens the Startup folder.
3. Inside this folder, create a new text file named `start_bot.bat` (make sure the extension is `.bat`, not `.txt`).
4. Right-click the file -> **Edit**, and paste this code:

```bat
@echo off
cd /d "C:\Path\To\Your\Bot\Folder"
pythonw bot.py
```

**Important:**
- Replace `C:\Path\To\Your\Bot\Folder` with the actual path where you downloaded the bot.
- `pythonw` (with a **w**) runs Python in the background without a black console window.
- If you installed dependencies in a virtual environment (optional), you might need to point to that python executable instead.

Now, every time you log in, the bot will start silently.

---

## ❓ Troubleshooting

**I don't see the slash commands (`/`)**
- It may take up to an hour for global commands to sync.
- Try kicking the bot and re-inviting it.
- Ensure `applications.commands` scope was selected when inviting.

**"Unauthorized" Error**
- The bot is hardcoded to only respond to the `OWNER_ID` specified in `.env`. This prevents others from controlling your PC.

**Where are my files?**
- Check `Documents/DiscordBot` (or your custom `BOT_DATA_DIR`). You will find `agenda.json`, `todo.json`, and `bot.log` there.

---

## 📜 License
This project is licensed under the **MIT License**.
Feel free to use, modify, and distribute it as you wish. See the [LICENSE](LICENSE) file for details.
