import os
from pathlib import Path

# Database on internal SSD (APFS) — ExFAT drives corrupt SQLite
DB_DIR = Path(os.environ.get("ARCHIVE_DB_DIR", os.path.expanduser("~/personal-archive-data")))
DB_PATH = DB_DIR / "archive.db"

# Attachments on fast external drive (individual file writes are fine on ExFAT)
ATTACHMENTS_DIR = Path(os.environ.get("ARCHIVE_ATTACHMENTS_DIR", "/Volumes/T9/personal-archive-data/attachments"))

# Photo thumbnails on internal SSD for speed
THUMBNAILS_DIR = DB_DIR / "thumbnails"

# Default mbox path
DEFAULT_MBOX_PATH = "/Volumes/Backup Plus/TakeOut/other product takeouts/All mail Including Spam and Trash-002.mbox"

# Default Google Photos Takeout paths
PHOTOS_TAKEOUT_BASE = "/Volumes/backup Plus/TakeOut/Zip Files"

# ffmpeg path
def get_ffmpeg_path():
    local_ffmpeg = os.path.expanduser("~/.local/bin/ffmpeg")
    if os.path.isfile(local_ffmpeg):
        return local_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"

# Server settings
HOST = "0.0.0.0"
PORT = 8000

# Ensure directories exist
def ensure_dirs():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
