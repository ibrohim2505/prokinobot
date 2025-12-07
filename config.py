import os

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

# Bot Token
BOT_TOKEN = _env("BOT_TOKEN", "8258174777:AAGkLwiKvDhgIcCiP8O8UhmIhay1kuiElmg")

# Admin ID
ADMIN_ID = _env_int("ADMIN_ID", 5425876649)

# Database fayli
DATABASE_PATH = _env("DATABASE_PATH", "database/movies.db")
