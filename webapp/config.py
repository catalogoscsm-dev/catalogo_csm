import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR        = Path(__file__).parent.parent
DATA_DIR        = BASE_DIR / "data"
DATA_OUTPUT_DIR = DATA_DIR / "output"
DB_PATH         = DATA_DIR / "catalog.db"

SECRET_KEY      = os.getenv("SECRET_KEY", "csm-catalog-secret-key-2025")
ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD", "admin123")
CLIENT_PASSWORD = os.getenv("CLIENT_PASSWORD", "cliente123")

USERS = {
    "admin":   {"password": ADMIN_PASSWORD,  "role": "admin"},
    "cliente": {"password": CLIENT_PASSWORD, "role": "client"},
}
