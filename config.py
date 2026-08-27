import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("TOKEN", "")).strip()
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAMID", os.getenv("ADMIN_TELEGRAM_ID", "0")) or "0")

WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8080/login").strip()
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0").strip()
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8080"))
ENABLE_WEBAPP_SERVER = os.getenv("ENABLE_WEBAPP_SERVER", "true").lower() in ("true", "1", "yes")

DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "users.db")).strip()

# Secret key for encrypting tokens in database
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    key_file = DATA_DIR / ".secret_key"
    if key_file.exists():
        SECRET_KEY = key_file.read_text().strip()
    else:
        from cryptography.fernet import Fernet
        SECRET_KEY = Fernet.generate_key().decode()
        key_file.write_text(SECRET_KEY)

REFRESH_INTERVAL_SEC = int(os.getenv("REFRESH_INTERVAL_SEC", "60"))
REFRESH_BEFORE_SEC = int(os.getenv("REFRESH_BEFORE_SEC", "600"))
DNEVNIK_API_URL = os.getenv("DNEVNIK_API_URL", "https://dnevnik.egov66.ru/api").rstrip("/")
SCHOOL_YEAR = os.getenv("SCHOOL_YEAR", os.getenv("FORCE_SCHOOL_YEAR", "")).strip()
TEST_SCHEDULE_DATE = os.getenv("TEST_SCHEDULE_DATE", "2025-05-12").strip()

# Настройки уведомлений о новых оценках
NOTIFY_INTERVAL_SEC = int(os.getenv("NOTIFY_INTERVAL_SEC", "2400"))  # 40 минут по умолчанию
NOTIFY_ENABLED = os.getenv("NOTIFY_ENABLED", "true").lower() in ("true", "1", "yes")
