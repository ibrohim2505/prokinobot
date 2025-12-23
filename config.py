import os
from dotenv import load_dotenv

# .env faylni yuklash
load_dotenv()

# Bot konfiguratsiyasi

def _env(key: str, default: str) -> str:
	value = os.getenv(key)
	return value if value not in (None, "") else default

def _env_int(key: str, default: int) -> int:
	value = os.getenv(key)
	if value is None or value == "":
		return default
	try:
		return int(value)
	except ValueError:
		return default

# Bot sozlamalari
BOT_TOKEN = _env('BOT_TOKEN', '')
ADMIN_ID = _env_int('ADMIN_ID', 0)
DATABASE_PATH = _env('DATABASE_PATH', 'database/movies.db')

# PostgreSQL sozlamalari (Railway uchun)
# Railway avtomatik DATABASE_URL environment variable beradi
DATABASE_URL = _env('DATABASE_URL', '')

# Database turini aniqlash
def is_postgres() -> bool:
    """PostgreSQL ishlatilayotganligini tekshirish"""
    return DATABASE_URL.startswith('postgres://') or DATABASE_URL.startswith('postgresql://')
