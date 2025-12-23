import sqlite3
import os
from typing import Optional, Tuple, List, Dict
from contextlib import contextmanager

from config import ADMIN_ID, DATABASE_URL, is_postgres

# PostgreSQL uchun
try:
    import psycopg2
    import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

DEFAULT_START_MESSAGE = (
    "👋 Salom, {first_name}!\n\n"
    "🎬 <b>Kino Bot</b>\n\n"
    "Kinoni olish uchun kino kodini yuboring.\n"
    "Kod faqat raqam va 1-10000 oralig'ida bo'lishi kerak.\n"
    "Masalan: <code>1</code>, <code>21</code>, <code>137</code>, <code>9999</code>\n\n"
    "{premium_hint}"
)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.use_postgres = is_postgres() and HAS_POSTGRES
        
        if not self.use_postgres:
            self._ensure_directory()
        
        self.init_database()

    def _ensure_directory(self):
        if self.use_postgres:
            return
        directory = os.path.dirname(os.path.abspath(self.db_path))
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def get_db_path(self) -> str:
        """Database faylining to'liq yo'lini qaytarish"""
        if self.use_postgres:
            return "PostgreSQL (Railway)"
        return os.path.abspath(self.db_path)
    
    @contextmanager
    def get_connection(self):
        """Database bilan bog'lanish (context manager)"""
        if self.use_postgres:
            # Railway PostgreSQL URL ni to'g'rilash
            url = DATABASE_URL
            if url.startswith('postgres://'):
                url = url.replace('postgres://', 'postgresql://', 1)
            conn = psycopg2.connect(url)
            try:
                yield conn
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(self.db_path)
            try:
                yield conn
            finally:
                conn.close()
    
    def _get_placeholder(self) -> str:
        """SQL placeholder - PostgreSQL uchun %s, SQLite uchun ?"""
        return "%s" if self.use_postgres else "?"
    
    def _adapt_sql(self, sql: str) -> str:
        """SQL ni database turiga moslashtirish"""
        if self.use_postgres:
            # SQLite ? ni PostgreSQL %s ga o'zgartirish
            sql = sql.replace("?", "%s")
            # AUTOINCREMENT -> SERIAL
            sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            # datetime funksiyalarini o'zgartirish
            sql = sql.replace("datetime('now')", "NOW()")
            sql = sql.replace("datetime('now', '-1 day')", "NOW() - INTERVAL '1 day'")
            sql = sql.replace("datetime('now', '-7 day')", "NOW() - INTERVAL '7 days'")
            # GLOB ni SIMILAR TO ga o'zgartirish
            sql = sql.replace("GLOB '[0-9]*'", "~ '^[0-9]+$'")
        return sql
    
    def init_database(self):
        """Database jadvallarini yaratish"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # PostgreSQL va SQLite uchun mos SQL
            if self.use_postgres:
                # PostgreSQL uchun jadvallar
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        id INTEGER PRIMARY KEY,
                        channel_id TEXT NOT NULL
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS movies (
                        id SERIAL PRIMARY KEY,
                        code TEXT UNIQUE NOT NULL,
                        message_id INTEGER NOT NULL,
                        channel_id TEXT NOT NULL,
                        movie_name TEXT,
                        movie_genre TEXT,
                        movie_duration INTEGER,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subscription_settings (
                        id INTEGER PRIMARY KEY,
                        is_enabled INTEGER DEFAULT 0,
                        subscription_message TEXT DEFAULT 'Botdan foydalanish uchun quyidagi kanallarga obuna boling:'
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subscription_channels (
                        id SERIAL PRIMARY KEY,
                        channel_id TEXT UNIQUE NOT NULL,
                        channel_name TEXT,
                        channel_username TEXT,
                        is_required INTEGER DEFAULT 1,
                        channel_type TEXT DEFAULT 'channel',
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS instagram_profiles (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        profile_name TEXT,
                        is_required INTEGER DEFAULT 1,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS channel_button (
                        id INTEGER PRIMARY KEY,
                        is_enabled INTEGER DEFAULT 1,
                        button_text TEXT DEFAULT '📢 Kanalimiz',
                        button_url TEXT DEFAULT 'https://t.me/YourChannelName'
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bot_messages (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name TEXT,
                        username TEXT,
                        language_code TEXT,
                        joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS admins (
                        user_id BIGINT PRIMARY KEY,
                        first_name TEXT,
                        username TEXT,
                        can_manage_movies INTEGER DEFAULT 1,
                        can_manage_channels INTEGER DEFAULT 0,
                        can_broadcast INTEGER DEFAULT 0,
                        can_manage_admins INTEGER DEFAULT 0,
                        can_manage_premium INTEGER DEFAULT 0,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_settings (
                        id INTEGER PRIMARY KEY,
                        is_active INTEGER DEFAULT 0,
                        description TEXT DEFAULT 'Premium obuna: Majburiy obuna talab etilmaydi',
                        price_1m INTEGER DEFAULT 12000,
                        price_3m INTEGER DEFAULT 36000,
                        price_6m INTEGER DEFAULT 60000,
                        price_12m INTEGER DEFAULT 110000,
                        card_info TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_users (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        first_name TEXT,
                        username TEXT,
                        plan TEXT,
                        expires_at TIMESTAMP,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_payments (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        amount INTEGER,
                        duration INTEGER,
                        payment_method TEXT,
                        reference TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_requests (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        first_name TEXT,
                        username TEXT,
                        plan_label TEXT,
                        duration INTEGER,
                        amount INTEGER,
                        status TEXT DEFAULT 'pending',
                        receipt_file_id TEXT,
                        receipt_file_type TEXT,
                        user_chat_id BIGINT,
                        receipt_message_id INTEGER,
                        admin_id BIGINT,
                        admin_comment TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            else:
                # SQLite uchun jadvallar
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        id INTEGER PRIMARY KEY,
                        channel_id TEXT NOT NULL
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS movies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT UNIQUE NOT NULL,
                        message_id INTEGER NOT NULL,
                        channel_id TEXT NOT NULL,
                        movie_name TEXT,
                        movie_genre TEXT,
                        movie_duration INTEGER,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subscription_settings (
                        id INTEGER PRIMARY KEY,
                        is_enabled INTEGER DEFAULT 0,
                        subscription_message TEXT DEFAULT 'Botdan foydalanish uchun quyidagi kanallarga obuna bo''ling:'
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subscription_channels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        channel_id TEXT UNIQUE NOT NULL,
                        channel_name TEXT,
                        channel_username TEXT,
                        is_required INTEGER DEFAULT 1,
                        channel_type TEXT DEFAULT 'channel',
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS instagram_profiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        profile_name TEXT,
                        is_required INTEGER DEFAULT 1,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS channel_button (
                        id INTEGER PRIMARY KEY,
                        is_enabled INTEGER DEFAULT 1,
                        button_text TEXT DEFAULT '📢 Kanalimiz',
                        button_url TEXT DEFAULT 'https://t.me/YourChannelName'
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bot_messages (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        first_name TEXT,
                        username TEXT,
                        language_code TEXT,
                        joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS admins (
                        user_id INTEGER PRIMARY KEY,
                        first_name TEXT,
                        username TEXT,
                        can_manage_movies INTEGER DEFAULT 1,
                        can_manage_channels INTEGER DEFAULT 0,
                        can_broadcast INTEGER DEFAULT 0,
                        can_manage_admins INTEGER DEFAULT 0,
                        can_manage_premium INTEGER DEFAULT 0,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_settings (
                        id INTEGER PRIMARY KEY,
                        is_active INTEGER DEFAULT 0,
                        description TEXT DEFAULT 'Premium obuna: Majburiy obuna talab etilmaydi',
                        price_1m INTEGER DEFAULT 12000,
                        price_3m INTEGER DEFAULT 36000,
                        price_6m INTEGER DEFAULT 60000,
                        price_12m INTEGER DEFAULT 110000,
                        card_info TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        first_name TEXT,
                        username TEXT,
                        plan TEXT,
                        expires_at TIMESTAMP,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        amount INTEGER,
                        duration INTEGER,
                        payment_method TEXT,
                        reference TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        first_name TEXT,
                        username TEXT,
                        plan_label TEXT,
                        duration INTEGER,
                        amount INTEGER,
                        status TEXT DEFAULT 'pending',
                        receipt_file_id TEXT,
                        receipt_file_type TEXT,
                        user_chat_id INTEGER,
                        receipt_message_id INTEGER,
                        admin_id INTEGER,
                        admin_comment TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            
            # Boshlang'ich ma'lumotlarni kiritish
            self._init_default_data(cursor)
            
            conn.commit()
    
    def _init_default_data(self, cursor):
        """Boshlang'ich ma'lumotlarni kiritish"""
        ph = self._get_placeholder()
        
        # Agar majburiy obuna sozlamalari bo'lmasa, yaratish
        cursor.execute("SELECT COUNT(*) FROM subscription_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO subscription_settings (id, is_enabled) VALUES (1, 0)")
        
        # Agar kanal tugmasi sozlamalari bo'lmasa, yaratish
        cursor.execute("SELECT COUNT(*) FROM channel_button")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO channel_button (id, is_enabled) VALUES (1, 1)")

        # Premium sozlamalarini boshlang'ich qiymat bilan yaratish
        cursor.execute("SELECT COUNT(*) FROM premium_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO premium_settings (id, is_active) VALUES (1, 0)")

        # /start xabarini saqlash uchun standart yozuv
        cursor.execute(f"SELECT COUNT(*) FROM bot_messages WHERE key = {ph}", ('start_message',))
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                f"INSERT INTO bot_messages (key, value) VALUES ({ph}, {ph})",
                ('start_message', DEFAULT_START_MESSAGE)
            )

        # Super adminni adminlar jadvaliga qo'shish
        cursor.execute(f"SELECT COUNT(*) FROM admins WHERE user_id = {ph}", (ADMIN_ID,))
        if cursor.fetchone()[0] == 0:
            cursor.execute(f'''
                INSERT INTO admins (user_id, first_name, username, can_manage_movies, can_manage_channels, can_broadcast, can_manage_admins, can_manage_premium)
                VALUES ({ph}, {ph}, {ph}, 1, 1, 1, 1, 1)
            ''', (ADMIN_ID, "Super Admin", None))
        
        # Migration: subscription_channels jadvaliga channel_type ustunini qo'shish
        try:
            if self.use_postgres:
                cursor.execute("""
                    ALTER TABLE subscription_channels 
                    ADD COLUMN IF NOT EXISTS channel_type TEXT DEFAULT 'channel'
                """)
            else:
                # SQLite uchun ustun borligini tekshirish
                cursor.execute("PRAGMA table_info(subscription_channels)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'channel_type' not in columns:
                    cursor.execute("""
                        ALTER TABLE subscription_channels 
                        ADD COLUMN channel_type TEXT DEFAULT 'channel'
                    """)
        except Exception as e:
            # Ustun allaqachon mavjud bo'lsa, o'tkazib yuborish
            pass
    
    def execute_query(self, query: str, params: tuple = (), fetch: str = None):
        """Universal SQL so'rov bajarish metodi
        
        Args:
            query: SQL so'rov (? placeholderlar bilan)
            params: So'rov parametrlari
            fetch: 'one' - bitta natija, 'all' - barcha natijalar, None - hech narsa
        
        Returns:
            fetch turiga qarab natija yoki None
        """
        try:
            # SQL ni database turiga moslashtirish
            adapted_query = self._adapt_sql(query)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(adapted_query, params)
                
                if fetch == 'one':
                    return cursor.fetchone()
                elif fetch == 'all':
                    return cursor.fetchall()
                else:
                    conn.commit()
                    return cursor.lastrowid if hasattr(cursor, 'lastrowid') else True
        except Exception as e:
            print(f"SQL xatolik: {e}")
            return None
    
    def set_channel(self, channel_id: str) -> bool:
        """Baza kanalini sozlash"""
        try:
            ph = self._get_placeholder()
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Avvalgi kanallarni o'chirish
                cursor.execute("DELETE FROM settings")
                
                # Yangi kanalni qo'shish
                cursor.execute(f"INSERT INTO settings (id, channel_id) VALUES (1, {ph})", (channel_id,))
                
                conn.commit()
            return True
        except Exception as e:
            print(f"Kanal sozlashda xatolik: {e}")
            return False
    
    def get_channel(self) -> Optional[str]:
        """Baza kanalini olish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT channel_id FROM settings WHERE id = 1")
                result = cursor.fetchone()
                
                if result:
                    return result[0]
                return None
        except Exception as e:
            print(f"Kanal olishda xatolik: {e}")
            return None
    
    def add_movie(self, code: str, message_id: int, channel_id: str, movie_name: str = None, movie_genre: str = None, movie_duration: int = None) -> bool:
        """Kinoni bazaga qo'shish"""
        try:
            result = self.execute_query(
                "INSERT INTO movies (code, message_id, channel_id, movie_name, movie_genre, movie_duration) VALUES (?, ?, ?, ?, ?, ?)",
                (code, message_id, channel_id, movie_name, movie_genre, movie_duration)
            )
            return result is not None
        except Exception as e:
            print(f"Kino qo'shishda xatolik: {e}")
            return False
    
    def get_movie(self, code: str) -> Optional[Tuple[int, str]]:
        """Kino kodiga qarab kinoni topish"""
        try:
            result = self.execute_query(
                "SELECT message_id, channel_id FROM movies WHERE code = ?",
                (code,),
                fetch='one'
            )
            return result
        except Exception as e:
            print(f"Kino topishda xatolik: {e}")
            return None
    
    def get_stats(self) -> dict:
        """Bot statistikasi uchun kengaytirilgan ma'lumotlar"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.use_postgres:
                    # PostgreSQL uchun
                    cursor.execute("SELECT COUNT(*) FROM movies")
                    total_movies = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM movies WHERE added_date >= NOW() - INTERVAL '1 day'")
                    movies_last_day = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM movies WHERE added_date >= NOW() - INTERVAL '7 days'")
                    movies_last_week = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM users")
                    total_users = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date >= NOW() - INTERVAL '1 day'")
                    users_last_day = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date >= NOW() - INTERVAL '7 days'")
                    users_last_week = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= NOW() - INTERVAL '1 day'")
                    active_users_day = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= NOW() - INTERVAL '7 days'")
                    active_users_week = cursor.fetchone()[0]
                else:
                    # SQLite uchun
                    cursor.execute("SELECT COUNT(*) FROM movies")
                    total_movies = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM movies WHERE added_date >= datetime('now', '-1 day')")
                    movies_last_day = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM movies WHERE added_date >= datetime('now', '-7 day')")
                    movies_last_week = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM users")
                    total_users = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date >= datetime('now', '-1 day')")
                    users_last_day = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date >= datetime('now', '-7 day')")
                    users_last_week = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= datetime('now', '-1 day')")
                    active_users_day = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= datetime('now', '-7 day')")
                    active_users_week = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT movie_name, code, added_date
                    FROM movies
                    ORDER BY added_date DESC
                    LIMIT 1
                """)
                last_movie_row = cursor.fetchone()

                cursor.execute("SELECT COUNT(*) FROM admins")
                total_admins = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM subscription_channels")
                subscription_channels = cursor.fetchone()[0]

            premium_stats = self.get_premium_stats()
            base_channel = self.get_channel()

            return {
                "total_movies": total_movies,
                "movies_last_24h": movies_last_day,
                "movies_last_7d": movies_last_week,
                "last_movie": {
                    "name": last_movie_row[0] if last_movie_row and last_movie_row[0] else "Noma'lum",
                    "code": last_movie_row[1] if last_movie_row else None,
                    "added_date": last_movie_row[2] if last_movie_row else None
                },
                "total_users": total_users,
                "users_last_24h": users_last_day,
                "users_last_7d": users_last_week,
                "active_users_24h": active_users_day,
                "active_users_7d": active_users_week,
                "total_admins": total_admins,
                "subscription_channels": subscription_channels,
                "base_channel": base_channel,
                "premium": premium_stats
            }
        except Exception as e:
            print(f"Statistika olishda xatolik: {e}")
            return {
                "total_movies": 0,
                "movies_last_24h": 0,
                "movies_last_7d": 0,
                "last_movie": {"name": None, "code": None, "added_date": None},
                "total_users": 0,
                "users_last_24h": 0,
                "users_last_7d": 0,
                "active_users_24h": 0,
                "active_users_7d": 0,
                "total_admins": 0,
                "subscription_channels": 0,
                "base_channel": None,
                "premium": {'total_users': 0, 'active_users': 0, 'total_payments': 0}
            }
    
    def get_next_movie_code(self) -> str:
        """Keyingi kino kodini olish (avtomatik)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Eng katta kod qiymatini topish
                cursor.execute("SELECT code FROM movies WHERE code GLOB '[0-9]*' ORDER BY CAST(code AS INTEGER) DESC LIMIT 1")
                result = cursor.fetchone()
                
                if result:
                    last_code = int(result[0])
                    return str(last_code + 1)
                else:
                    return "1"  # Birinchi kino
        except Exception as e:
            print(f"Kod olishda xatolik: {e}")
            return "1"
    
    def is_code_exists(self, code: str) -> bool:
        """Kod mavjudligini tekshirish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM movies WHERE code = ?", (code,))
                count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            print(f"Kod tekshirishda xatolik: {e}")
            return False
    
    def get_subscription_status(self) -> bool:
        """Majburiy obuna holatini olish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_enabled FROM subscription_settings WHERE id = 1")
                result = cursor.fetchone()
            return bool(result[0]) if result else False
        except Exception as e:
            print(f"Obuna holatini olishda xatolik: {e}")
            return False

    def get_start_message(self) -> str:
        """Foydalanuvchilarga yuboriladigan /start xabarini olish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM bot_messages WHERE key = 'start_message'")
                result = cursor.fetchone()
            if result and result[0]:
                return result[0]
            return DEFAULT_START_MESSAGE
        except Exception as e:
            print(f"/start xabarini olishda xatolik: {e}")
            return DEFAULT_START_MESSAGE

    def update_start_message(self, message: str) -> bool:
        """/start xabarini yangilash"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO bot_messages (key, value) VALUES ('start_message', ?)",
                    (message,)
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"/start xabarini yangilashda xatolik: {e}")
            return False
    
    def set_subscription_status(self, is_enabled: bool) -> bool:
        """Majburiy obuna holatini o'zgartirish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE subscription_settings SET is_enabled = ? WHERE id = 1", (1 if is_enabled else 0,))
                conn.commit()
            return True
        except Exception as e:
            print(f"Obuna holatini o'zgartirishda xatolik: {e}")
            return False
    
    def add_subscription_channel(self, channel_id: str, channel_name: str = None, channel_username: str = None, is_required: bool = True, channel_type: str = 'channel') -> bool:
        """Kanal/havola qo'shish
        
        Args:
            channel_id: Kanal ID yoki havola URL
            channel_name: Kanal nomi
            channel_username: Kanal username
            is_required: Majburiy/Ixtiyoriy
            channel_type: 'channel' (oddiy), 'request' (so'rovli), 'link' (havola)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = self._adapt_sql(
                    "INSERT INTO subscription_channels (channel_id, channel_name, channel_username, is_required, channel_type) VALUES (?, ?, ?, ?, ?)"
                )
                cursor.execute(
                    sql,
                    (channel_id, channel_name, channel_username, 1 if is_required else 0, channel_type)
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"Kanal qo'shishda xatolik: {e}")
            return False
    
    def get_subscription_channels(self) -> list:
        """Barcha kanallar va havolalarni olish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = self._adapt_sql("SELECT channel_id, channel_name, channel_username, is_required, channel_type FROM subscription_channels")
                cursor.execute(sql)
                results = cursor.fetchall()
            return results
        except Exception as e:
            print(f"Kanallarni olishda xatolik: {e}")
            return []
    
    def get_required_channels(self) -> list:
        """Faqat majburiy kanallarni olish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT channel_id, channel_name, channel_username FROM subscription_channels WHERE is_required = 1")
                results = cursor.fetchall()
            return results
        except Exception as e:
            print(f"Majburiy kanallarni olishda xatolik: {e}")
            return []
    
    def update_channel_required_status(self, channel_id: str, is_required: bool) -> bool:
        """Kanalning majburiy/ixtiyoriy holatini o'zgartirish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE subscription_channels SET is_required = ? WHERE channel_id = ?", (1 if is_required else 0, channel_id))
                conn.commit()
            return True
        except Exception as e:
            print(f"Kanal holatini o'zgartirishda xatolik: {e}")
            return False
    
    def delete_subscription_channel(self, channel_id: str) -> bool:
        """Majburiy obuna kanalini o'chirish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM subscription_channels WHERE channel_id = ?", (channel_id,))
                conn.commit()
            return True
        except Exception as e:
            print(f"Kanalni o'chirishda xatolik: {e}")
            return False
    
    # Instagram profil metodlari
    def add_instagram_profile(self, username: str, profile_name: str = None, is_required: bool = True) -> bool:
        """Instagram profil qo'shish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # @ belgisini olib tashlash
                username = username.lstrip('@')
                cursor.execute(
                    "INSERT INTO instagram_profiles (username, profile_name, is_required) VALUES (?, ?, ?)",
                    (username, profile_name, 1 if is_required else 0)
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"Instagram profil qo'shishda xatolik: {e}")
            return False
    
    def get_instagram_profiles(self) -> list:
        """Barcha Instagram profillarni olish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, username, profile_name, is_required FROM instagram_profiles")
                results = cursor.fetchall()
            return results
        except Exception as e:
            print(f"Instagram profillarni olishda xatolik: {e}")
            return []
    
    def get_required_instagram_profiles(self) -> list:
        """Faqat majburiy Instagram profillarni olish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, username, profile_name FROM instagram_profiles WHERE is_required = 1")
                results = cursor.fetchall()
            return results
        except Exception as e:
            print(f"Majburiy Instagram profillarni olishda xatolik: {e}")
            return []
    
    def delete_instagram_profile(self, profile_id: int) -> bool:
        """Instagram profilni o'chirish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM instagram_profiles WHERE id = ?", (profile_id,))
                conn.commit()
            return True
        except Exception as e:
            print(f"Instagram profilni o'chirishda xatolik: {e}")
            return False
    
    def update_instagram_required_status(self, profile_id: int, is_required: bool) -> bool:
        """Instagram profilning majburiy/ixtiyoriy holatini o'zgartirish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE instagram_profiles SET is_required = ? WHERE id = ?", (1 if is_required else 0, profile_id))
                conn.commit()
            return True
        except Exception as e:
            print(f"Instagram profil holatini o'zgartirishda xatolik: {e}")
            return False
    
    def get_subscription_message(self) -> str:
        """Obuna xabarini olish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT subscription_message FROM subscription_settings WHERE id = 1")
                result = cursor.fetchone()
            return result[0] if result else "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:"
        except Exception as e:
            print(f"Obuna xabarini olishda xatolik: {e}")
            return "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:"
    
    def update_subscription_message(self, message: str) -> bool:
        """Obuna xabarini yangilash"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE subscription_settings SET subscription_message = ? WHERE id = 1", (message,))
                conn.commit()
            return True
        except Exception as e:
            print(f"Obuna xabarini yangilashda xatolik: {e}")
            return False
    
    # Kanal tugmasi metodlari
    def get_channel_button(self) -> dict:
        """Kanal tugmasi sozlamalarini olish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_enabled, button_text, button_url FROM channel_button WHERE id = 1")
                result = cursor.fetchone()
            if result:
                return {
                    'is_enabled': bool(result[0]),
                    'button_text': result[1],
                    'button_url': result[2]
                }
            return {'is_enabled': True, 'button_text': '📢 Kanalimiz', 'button_url': 'https://t.me/YourChannelName'}
        except Exception as e:
            print(f"Kanal tugmasi sozlamalarini olishda xatolik: {e}")
            return {'is_enabled': True, 'button_text': '📢 Kanalimiz', 'button_url': 'https://t.me/YourChannelName'}
    
    def toggle_channel_button(self) -> bool:
        """Kanal tugmasini yoqish/o'chirish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_enabled FROM channel_button WHERE id = 1")
                current = cursor.fetchone()[0]
                new_value = 0 if current else 1
                cursor.execute("UPDATE channel_button SET is_enabled = ? WHERE id = 1", (new_value,))
                conn.commit()
            return bool(new_value)
        except Exception as e:
            print(f"Kanal tugmasini o'zgartirishda xatolik: {e}")
            return False
    
    def update_channel_button(self, button_text: str = None, button_url: str = None) -> bool:
        """Kanal tugmasini yangilash"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if button_text and button_url:
                    cursor.execute("UPDATE channel_button SET button_text = ?, button_url = ? WHERE id = 1", (button_text, button_url))
                elif button_text:
                    cursor.execute("UPDATE channel_button SET button_text = ? WHERE id = 1", (button_text,))
                elif button_url:
                    cursor.execute("UPDATE channel_button SET button_url = ? WHERE id = 1", (button_url,))
                
                conn.commit()
            return True
        except Exception as e:
            print(f"Kanal tugmasini yangilashda xatolik: {e}")
            return False
    
    def set_subscription_message(self, message: str) -> bool:
        """Obuna xabarini o'zgartirish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE subscription_settings SET subscription_message = ? WHERE id = 1", (message,))
                conn.commit()
            return True
        except Exception as e:
            print(f"Obuna xabarini o'zgartirishda xatolik: {e}")
            return False

    def upsert_user(self, user_id: int, first_name: str = None, username: str = None, language_code: str = None) -> None:
        """Foydalanuvchini bazaga qo'shish yoki yangilash"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (user_id, first_name, username, language_code)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        first_name = excluded.first_name,
                        username = excluded.username,
                        language_code = excluded.language_code,
                        last_active = CURRENT_TIMESTAMP
                ''', (user_id, first_name, username, language_code))
                conn.commit()
        except Exception as e:
            print(f"Foydalanuvchini saqlashda xatolik: {e}")

    def get_all_users(self) -> List[int]:
        """Broadcast uchun barcha foydalanuvchi ID larini olish"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users")
                rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            print(f"Foydalanuvchilarni olishda xatolik: {e}")
            return []

    # Admin boshqaruvi metodlari
    def is_admin_user(self, user_id: int) -> bool:
        if user_id == ADMIN_ID:
            return True
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
            return result is not None
        except Exception as e:
            print(f"Admin tekshirishda xatolik: {e}")
            return False

    def get_admins(self) -> List[Dict]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, first_name, username,
                           can_manage_movies, can_manage_channels,
                           can_broadcast, can_manage_admins,
                           can_manage_premium
                    FROM admins
                    ORDER BY added_date ASC
                ''')
                rows = cursor.fetchall()
            admins = []
            for row in rows:
                admins.append({
                    'user_id': row[0],
                    'first_name': row[1],
                    'username': row[2],
                    'can_manage_movies': bool(row[3]),
                    'can_manage_channels': bool(row[4]),
                    'can_broadcast': bool(row[5]),
                    'can_manage_admins': bool(row[6]),
                    'can_manage_premium': bool(row[7])
                })
            return admins
        except Exception as e:
            print(f"Adminlar ro'yxatini olishda xatolik: {e}")
            return []

    def add_admin_user(self, user_id: int, first_name: str = None, username: str = None) -> bool:
        if user_id == ADMIN_ID:
            return True
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO admins (user_id, first_name, username)
                    VALUES (?, ?, ?)
                ''', (user_id, first_name, username))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            print(f"Admin qo'shishda xatolik: {e}")
            return False

    def remove_admin_user(self, user_id: int) -> bool:
        if user_id == ADMIN_ID:
            return False
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
                conn.commit()
                deleted = cursor.rowcount > 0
            return deleted
        except Exception as e:
            print(f"Adminni o'chirishda xatolik: {e}")
            return False

    def get_admin(self, user_id: int) -> Optional[Dict]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, first_name, username,
                           can_manage_movies, can_manage_channels,
                           can_broadcast, can_manage_admins,
                           can_manage_premium
                    FROM admins WHERE user_id = ?
                ''', (user_id,))
                row = cursor.fetchone()
            if not row:
                if user_id == ADMIN_ID:
                    return {
                        'user_id': ADMIN_ID,
                        'first_name': 'Super Admin',
                        'username': None,
                        'can_manage_movies': True,
                        'can_manage_channels': True,
                        'can_broadcast': True,
                        'can_manage_admins': True,
                        'can_manage_premium': True
                    }
                return None
            return {
                'user_id': row[0],
                'first_name': row[1],
                'username': row[2],
                'can_manage_movies': bool(row[3]),
                'can_manage_channels': bool(row[4]),
                'can_broadcast': bool(row[5]),
                'can_manage_admins': bool(row[6]),
                'can_manage_premium': bool(row[7])
            }
        except Exception as e:
            print(f"Admin ma'lumotlarini olishda xatolik: {e}")
            return None

    def update_admin_permissions(self, user_id: int, **permissions) -> bool:
        if user_id == ADMIN_ID:
            return False
        valid_columns = {
            'can_manage_movies',
            'can_manage_channels',
            'can_broadcast',
            'can_manage_admins',
            'can_manage_premium'
        }
        fields = []
        values = []
        for key, value in permissions.items():
            if key in valid_columns:
                fields.append(f"{key} = ?")
                values.append(1 if value else 0)
        if not fields:
            return False
        values.append(user_id)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE admins SET {', '.join(fields)} WHERE user_id = ?", values)
                conn.commit()
                updated = cursor.rowcount > 0
            return updated
        except Exception as e:
            print(f"Admin huquqlarini yangilashda xatolik: {e}")
            return False

    def user_has_permission(self, user_id: int, permission: str) -> bool:
        if user_id == ADMIN_ID:
            return True
        column_map = {
            'movies': 'can_manage_movies',
            'channels': 'can_manage_channels',
            'broadcast': 'can_broadcast',
            'admins': 'can_manage_admins',
            'premium': 'can_manage_premium'
        }
        column = column_map.get(permission)
        if not column:
            return False
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT {column} FROM admins WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
            return bool(row[0]) if row else False
        except Exception as e:
            print(f"Huquq tekshirishda xatolik: {e}")
            return False

    # Premium obuna metodlari
    def get_premium_settings(self) -> Dict:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT is_active, description,
                           price_1m, price_3m, price_6m, price_12m,
                           card_info
                    FROM premium_settings WHERE id = 1
                ''')
                row = cursor.fetchone()
                if not row:
                    cursor.execute("""
                        INSERT INTO premium_settings (id, is_active)
                        VALUES (1, 0)
                    """)
                    conn.commit()
                    cursor.execute('''
                        SELECT is_active, description,
                               price_1m, price_3m, price_6m, price_12m,
                               card_info
                        FROM premium_settings WHERE id = 1
                    ''')
                    row = cursor.fetchone()
            return {
                'is_active': bool(row[0]),
                'description': row[1],
                'price_1m': row[2],
                'price_3m': row[3],
                'price_6m': row[4],
                'price_12m': row[5],
                'card_info': row[6]
            }
        except Exception as e:
            print(f"Premium sozlamalarini olishda xatolik: {e}")
            return {
                'is_active': False,
                'description': 'Premium obuna: Majburiy obuna talab etilmaydi',
                'price_1m': 12000,
                'price_3m': 36000,
                'price_6m': 60000,
                'price_12m': 110000,
                'card_info': None
            }

    def update_premium_prices(self, price_1m: int, price_3m: int, price_6m: int, price_12m: int) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE premium_settings
                    SET price_1m = ?, price_3m = ?, price_6m = ?, price_12m = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''', (price_1m, price_3m, price_6m, price_12m))
                conn.commit()
            return True
        except Exception as e:
            print(f"Premium narxlarini yangilashda xatolik: {e}")
            return False

    def update_premium_description(self, description: str) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE premium_settings
                    SET description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''', (description.strip(),))
                conn.commit()
            return True
        except Exception as e:
            print(f"Premium tavsifini yangilashda xatolik: {e}")
            return False

    def toggle_premium_status(self) -> Optional[bool]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_active FROM premium_settings WHERE id = 1")
                current = cursor.fetchone()
                current_value = bool(current[0]) if current else False
                new_value = 0 if current_value else 1
                cursor.execute('''
                    UPDATE premium_settings
                    SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''', (new_value,))
                conn.commit()
            return bool(new_value)
        except Exception as e:
            print(f"Premium holatini o'zgartirishda xatolik: {e}")
            return None

    def update_premium_card(self, card_info: str) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE premium_settings
                    SET card_info = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''', (card_info.strip(),))
                conn.commit()
            return True
        except Exception as e:
            print(f"Karta ma'lumotlarini yangilashda xatolik: {e}")
            return False

    def get_premium_stats(self) -> Dict:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM premium_users")
                total_users = cursor.fetchone()[0]
                cursor.execute("""
                    SELECT COUNT(*) FROM premium_users
                    WHERE expires_at IS NULL OR datetime(expires_at) >= datetime('now')
                """)
                active_users = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM premium_payments")
                payments = cursor.fetchone()[0]
            return {
                'total_users': total_users,
                'active_users': active_users,
                'total_payments': payments
            }
        except Exception as e:
            print(f"Premium statistikani olishda xatolik: {e}")
            return {'total_users': 0, 'active_users': 0, 'total_payments': 0}

    def get_premium_users(self, limit: int = 10) -> List[Dict]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, first_name, username, plan, expires_at, joined_at
                    FROM premium_users
                    ORDER BY joined_at DESC
                    LIMIT ?
                ''', (limit,))
                rows = cursor.fetchall()
            users = []
            for row in rows:
                users.append({
                    'user_id': row[0],
                    'first_name': row[1],
                    'username': row[2],
                    'plan': row[3],
                    'expires_at': row[4],
                    'joined_at': row[5]
                })
            return users
        except Exception as e:
            print(f"Premium foydalanuvchilarni olishda xatolik: {e}")
            return []

    def get_premium_payments(self, limit: int = 10) -> List[Dict]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, amount, duration, payment_method, reference, created_at
                    FROM premium_payments
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
                rows = cursor.fetchall()
            payments = []
            for row in rows:
                payments.append({
                    'user_id': row[0],
                    'amount': row[1],
                    'duration': row[2],
                    'payment_method': row[3],
                    'reference': row[4],
                    'created_at': row[5]
                })
            return payments
        except Exception as e:
            print(f"Premium to'lovlarini olishda xatolik: {e}")
            return []

    def create_premium_request(
        self,
        user_id: int,
        first_name: Optional[str],
        username: Optional[str],
        plan_label: str,
        duration: int,
        amount: Optional[int],
        receipt_file_id: str,
        receipt_file_type: str,
        user_chat_id: int,
        receipt_message_id: int
    ) -> Optional[int]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO premium_requests (
                        user_id, first_name, username,
                        plan_label, duration, amount,
                        receipt_file_id, receipt_file_type,
                        user_chat_id, receipt_message_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    first_name,
                    username,
                    plan_label,
                    duration,
                    amount,
                    receipt_file_id,
                    receipt_file_type,
                    user_chat_id,
                    receipt_message_id
                ))
                conn.commit()
                request_id = cursor.lastrowid
            return request_id
        except Exception as e:
            print(f"Premium so'rovini yaratishda xatolik: {e}")
            return None

    def get_premium_request(self, request_id: int) -> Optional[Dict]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, user_id, first_name, username,
                           plan_label, duration, amount, status,
                           receipt_file_id, receipt_file_type,
                           user_chat_id, receipt_message_id,
                           admin_id, admin_comment, created_at, updated_at
                    FROM premium_requests
                    WHERE id = ?
                ''', (request_id,))
                row = cursor.fetchone()
            if not row:
                return None
            return {
                'id': row[0],
                'user_id': row[1],
                'first_name': row[2],
                'username': row[3],
                'plan_label': row[4],
                'duration': row[5],
                'amount': row[6],
                'status': row[7],
                'receipt_file_id': row[8],
                'receipt_file_type': row[9],
                'user_chat_id': row[10],
                'receipt_message_id': row[11],
                'admin_id': row[12],
                'admin_comment': row[13],
                'created_at': row[14],
                'updated_at': row[15]
            }
        except Exception as e:
            print(f"Premium so'rovini olishda xatolik: {e}")
            return None

    def update_premium_request_status(
        self,
        request_id: int,
        status: str,
        admin_id: Optional[int] = None,
        admin_comment: Optional[str] = None
    ) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE premium_requests
                    SET status = ?,
                        admin_id = ?,
                        admin_comment = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, admin_id, admin_comment, request_id))
                conn.commit()
                updated = cursor.rowcount > 0
            return updated
        except Exception as e:
            print(f"Premium so'rov holatini yangilashda xatolik: {e}")
            return False


