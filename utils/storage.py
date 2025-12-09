import json
import os
import datetime
import shutil
import io
import csv
import logging
from utils import config

logger = logging.getLogger("discordbot")

def load_events():
    try:
        if not os.path.exists(config.AGENDA_FILE):
            return []
        with open(config.AGENDA_FILE, 'r', encoding='utf-8') as f:
            events_raw = json.load(f)
            for event in events_raw:
                if 'datetime_evento' in event:
                    event['datetime_evento'] = datetime.datetime.fromisoformat(event['datetime_evento'])
                elif 'data_evento' in event:  # Legacy compatibility
                    event['datetime_evento'] = datetime.datetime.strptime(event['data_evento'], "%Y-%m-%d")
            return events_raw
    except Exception as e:
        logger.exception(f"Error loading events: {e}")
        return []

def save_events(events):
    try:
        os.makedirs(os.path.dirname(config.AGENDA_FILE), exist_ok=True)
        events_to_save = []
        for event in events:
            copy_event = event.copy()
            copy_event['datetime_evento'] = copy_event['datetime_evento'].isoformat()
            copy_event.pop('data_evento', None)
            events_to_save.append(copy_event)
        with open(config.AGENDA_FILE, 'w', encoding='utf-8') as f:
            json.dump(events_to_save, f, indent=2, ensure_ascii=False)
        logger.info(f"Events saved to: {config.AGENDA_FILE}")
        return True
    except Exception as e:
        logger.exception(f"Error saving events: {e}")
        return False

def load_todo():
    try:
        if not os.path.exists(config.TODO_FILE):
            return []
        with open(config.TODO_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.exception(f"Error loading todo: {e}")
        return []

def save_todo(items):
    try:
        os.makedirs(os.path.dirname(config.TODO_FILE), exist_ok=True)
        # Backup previous file
        if os.path.exists(config.TODO_FILE):
            try:
                # create backup with timestamp
                bak_name = config.TODO_FILE + ".bak." + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                os.replace(config.TODO_FILE, bak_name)
                # cleanup: keep only last N backups
                try:
                    bak_dir = os.path.dirname(config.TODO_FILE)
                    prefix = os.path.basename(config.TODO_FILE) + ".bak."
                    bak_files = [f for f in os.listdir(bak_dir) if f.startswith(prefix)]
                    # sort by name (timestamp) descending
                    bak_files.sort(reverse=True)
                    keep = 5
                    for old in bak_files[keep:]:
                        try:
                            os.remove(os.path.join(bak_dir, old))
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception:
                # non-fatal
                pass

        tmp_path = config.TODO_FILE + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        # atomic replace
        os.replace(tmp_path, config.TODO_FILE)
        logger.info(f"To-Do saved to: {config.TODO_FILE}")
        return True
    except Exception as e:
        logger.exception(f"Error saving todo: {e}")
        return False

def load_secret_2fa():
    if not os.path.exists(config.SECRET_2FA_FILE):
        return None
    try:
        with open(config.SECRET_2FA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('secret')
    except Exception:
        return None

def save_secret_2fa(secret):
    try:
        with open(config.SECRET_2FA_FILE, 'w', encoding='utf-8') as f:
            json.dump({'secret': secret}, f)
        return True
    except Exception:
        return False

def create_backup_file(file_path: str, keep: int = 10) -> str:
    """Creates a timestamped backup of the file and returns the backup path.
    Keeps at most `keep` recent backups.
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        dirp = os.path.dirname(file_path)
        base = os.path.basename(file_path)
        bak_dir = os.path.join(dirp, f".{base}.backups")
        os.makedirs(bak_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        bak_name = f"{base}.bak.{stamp}"
        bak_path = os.path.join(bak_dir, bak_name)
        shutil.copy2(file_path, bak_path)

        # rotation
        files = sorted([f for f in os.listdir(bak_dir) if f.startswith(base + '.bak.')], reverse=True)
        for old in files[keep:]:
            try:
                os.remove(os.path.join(bak_dir, old))
            except Exception:
                pass

        return bak_path
    except Exception as e:
        logger.exception(f"Error create_backup_file: {e}")
        raise

def list_backups(file_path: str):
    dirp = os.path.dirname(file_path)
    base = os.path.basename(file_path)
    bak_dir = os.path.join(dirp, f".{base}.backups")
    if not os.path.exists(bak_dir):
        return []
    items = sorted([f for f in os.listdir(bak_dir) if f.startswith(base + '.bak.')], reverse=True)
    return items

def restore_backup(file_path: str, backup_filename: str) -> bool:
    dirp = os.path.dirname(file_path)
    base = os.path.basename(file_path)
    bak_dir = os.path.join(dirp, f".{base}.backups")
    bak_path = os.path.join(bak_dir, backup_filename)
    if not os.path.exists(bak_path):
        raise FileNotFoundError(bak_path)
    tmp_restore = file_path + ".restore.tmp"
    shutil.copy2(bak_path, tmp_restore)
    os.replace(tmp_restore, file_path)
    return True

def todo_to_csv(items):
    """Returns CSV bytes for todo list."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'user_id', 'text', 'created', 'done', 'done_at'])
    for it in items:
        writer.writerow([
            it.get('id', ''),
            it.get('user_id', ''),
            it.get('text', '').replace('\n', ' '),
            it.get('created', ''),
            str(bool(it.get('done', False))),
            it.get('done_at', '')
        ])
    return output.getvalue().encode('utf-8')
