import re
import datetime
from datetime import timedelta
import aiohttp
import urllib.parse
import asyncio
import platform
import tempfile
import os
import shutil
import logging

# Optional dependencies
try:
    import psutil
except ImportError:
    psutil = None

try:
    import mss
except ImportError:
    mss = None

logger = logging.getLogger("discordbot")

def parse_time(time_str):
    """
    Parses a time string and returns a timedelta.
    Supports: s (seconds), m (minutes), h (hours), d (days)
    """
    match = re.match(r'^\s*(\d+)\s*([smhd])\s*$', time_str.lower())
    if not match:
        return None
    number, unit = int(match.group(1)), match.group(2)
    if unit == 's': return timedelta(seconds=number)
    if unit == 'm': return timedelta(minutes=number)
    if unit == 'h': return timedelta(hours=number)
    if unit == 'd': return timedelta(days=number)
    return None

def get_weather_description(code):
    wmo_codes = {
        0: ("☀️", "Clear sky"), 1: ("🌤️", "Mainly clear"), 2: ("⛅", "Partly cloudy"),
        3: ("☁️", "Overcast"), 45: ("🌫️", "Fog"), 48: ("🌫️", "Depositing rime fog"),
        51: ("🌧️", "Light drizzle"), 53: ("🌧️", "Moderate drizzle"), 55: ("🌧️", "Dense drizzle"),
        56: ("🌨️", "Light freezing drizzle"), 57: ("🌨️", "Dense freezing drizzle"),
        61: ("💧", "Light rain"), 63: ("💧", "Moderate rain"), 65: ("💧", "Heavy rain"),
        66: ("❄️", "Light freezing rain"), 67: ("❄️", "Heavy freezing rain"),
        71: ("🌨️", "Light snow fall"), 73: ("🌨️", "Moderate snow fall"), 75: ("🌨️", "Heavy snow fall"),
        77: ("❄️", "Snow grains"), 80: ("🌦️", "Light rain showers"), 81: ("🌦️", "Moderate rain showers"),
        82: ("⛈️", "Violent rain showers"), 85: ("🌨️", "Light snow showers"), 86: ("🌨️", "Heavy snow showers"),
        95: ("🌩️", "Thunderstorm"), 96: ("⛈️", "Thunderstorm with light hail"), 99: ("⛈️", "Thunderstorm with heavy hail")
    }
    return wmo_codes.get(code, ("🤔", "Unknown"))

def get_wind_direction(degrees):
    if degrees is None:
        return "N/A"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = round(degrees / (360. / len(dirs)))
    return dirs[ix % len(dirs)]

def format_bytes(num):
    step = 1024.0
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if num < step:
            return f"{num:.1f} {unit}"
        num /= step
    return f"{num:.1f} PB"

async def generate_qr_code(text):
    """Generates a QR code using qr-server.com API"""
    try:
        encoded_text = urllib.parse.quote(text)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_text}"
        async with aiohttp.ClientSession() as session:
            async with session.get(qr_url) as response:
                if response.status == 200:
                    return await response.read()
                return None
    except Exception as e:
        logger.exception(f"Error generating QR code: {e}")
        return None

async def shorten_url(url):
    """Shortens a URL using is.gd API"""
    try:
        async with aiohttp.ClientSession() as session:
            api_url = "https://is.gd/create.php"
            params = {'format': 'simple', 'url': url}
            async with session.get(api_url, params=params) as response:
                if response.status == 200:
                    shortened_url = await response.text()
                    if shortened_url.startswith('http'):
                        return shortened_url.strip()
                return None
    except Exception as e:
        logger.exception(f"Error shortening URL: {e}")
        return None

async def run_system_command(cmd):
    """Executes a system command asynchronously and returns (rc, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, (stdout or b"").decode().strip(), (stderr or b"").decode().strip()
    except Exception as e:
        return -1, "", str(e)

def _capture_screenshot_bytes_sync():
    if platform.system() != "Windows":
        raise RuntimeError("Screenshot command available only on Windows.")
    if mss is None:
        raise RuntimeError("'mss' module missing. Install with 'pip install mss'.")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp_path = tmp.name
    tmp.close()
    try:
        with mss.mss() as sct:
            sct.shot(mon=-1, output=tmp_path)
        with open(tmp_path, "rb") as f:
            data = f.read()
        return data
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

def _collect_system_status_sync():
    info = {}
    info['platform'] = platform.platform()
    info['python'] = platform.python_version()
    info['hostname'] = platform.node()
    info['psutil_available'] = psutil is not None
    if psutil:
        boot = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime_delta = datetime.datetime.now() - boot
        info['uptime'] = uptime_delta
        info['cpu_percent'] = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        info['memory'] = {
            'used': mem.used,
            'total': mem.total,
            'percent': mem.percent
        }
        info['processes'] = len(psutil.pids())
    else:
        info['uptime'] = None
        info['cpu_percent'] = None
        info['memory'] = None
        info['processes'] = None
    root_path = os.path.splitdrive(os.path.abspath(os.sep))[0] + os.sep
    try:
        disk = shutil.disk_usage(root_path)
        info['disk'] = {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free
        }
    except Exception:
        info['disk'] = None
    return info
