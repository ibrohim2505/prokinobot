import sqlite3
import os
from typing import Optional, Tuple, List, Dict

from config import ADMIN_ID

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
        self._ensure_directory()
        self.init_database()

    def _ensure_directory(self):
        directory = os.path.dirname(os.path.abspath(self.db_path))
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def get_db_path(self) -> str:
        """Database faylining to'liq yo'lini qaytarish"""
        return os.path.abspath(self.db_path)
    
    def get_connection(self):
        """Database bilan bog'lanish"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Database jadvallarini yaratish"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Sozlamalar jadvali (baza kanal)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                channel_id TEXT NOT NULL
            )
        ''')
        
        # Kinolar jadvali
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
        
        # Majburiy obuna sozlamalari
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscription_settings (
                id INTEGER PRIMARY KEY,
                is_enabled INTEGER DEFAULT 0,
                subscription_message TEXT DEFAULT 'Botdan foydalanish uchun quyidagi kanallarga obuna bo''ling:'
            )
        ''')
        
        # Majburiy obuna kanallari
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscription_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE NOT NULL,
                channel_name TEXT,
                channel_username TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Kanal tugmasi sozlamalari
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_button (
                id INTEGER PRIMARY KEY,
                is_enabled INTEGER DEFAULT 1,
                button_text TEXT DEFAULT '📢 Kanalimiz',
                button_url TEXT DEFAULT 'https://t.me/YourChannelName'
            )
        ''')

        # Bot xabarlari jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_messages (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # Foydalanuvchilar ro'yxati (broadcast uchun)
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

        # Adminlar jadvali
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

        # Premium obuna jadvallari
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
            cursor.execute("""
                INSERT INTO premium_settings (id, is_active)
                VALUES (1, 0)
            """)

        # Eski bazalar uchun qo'shimcha ustunni kiritish
        cursor.execute("PRAGMA table_info(admins)")
        admin_columns = {row[1] for row in cursor.fetchall()}
        if 'can_manage_premium' not in admin_columns:
            cursor.execute("ALTER TABLE admins ADD COLUMN can_manage_premium INTEGER DEFAULT 0")

        # /start xabarini saqlash uchun standart yozuv
        cursor.execute("SELECT COUNT(*) FROM bot_messages WHERE key = 'start_message'")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO bot_messages (key, value) VALUES ('start_message', ?)",
                (DEFAULT_START_MESSAGE,)
            )

        # Super adminni adminlar jadvaliga qo'shish
        cursor.execute("SELECT COUNT(*) FROM admins WHERE user_id = ?", (ADMIN_ID,))
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO admins (user_id, first_name, username, can_manage_movies, can_manage_channels, can_broadcast, can_manage_admins, can_manage_premium)
                VALUES (?, ?, ?, 1, 1, 1, 1, 1)
            ''', (ADMIN_ID, "Super Admin", None))
        
        conn.commit()
        conn.close()
    
    def set_channel(self, channel_id: str) -> bool:
        """Baza kanalini sozlash"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Avvalgi kanallarni o'chirish
            cursor.execute("DELETE FROM settings")
            
            # Yangi kanalni qo'shish
            cursor.execute("INSERT INTO settings (id, channel_id) VALUES (1, ?)", (channel_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Kanal sozlashda xatolik: {e}")
            return False
    
    def get_channel(self) -> Optional[str]:
        """Baza kanalini olish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT channel_id FROM settings WHERE id = 1")
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                return result[0]
            return None
        except Exception as e:
            print(f"Kanal olishda xatolik: {e}")
            return None
    
    def add_movie(self, code: str, message_id: int, channel_id: str, movie_name: str = None, movie_genre: str = None, movie_duration: int = None) -> bool:
        """Kinoni bazaga qo'shish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO movies (code, message_id, channel_id, movie_name, movie_genre, movie_duration) VALUES (?, ?, ?, ?, ?, ?)",
                (code, message_id, channel_id, movie_name, movie_genre, movie_duration)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Kino qo'shishda xatolik: {e}")
            return False
    
    def get_movie(self, code: str) -> Optional[Tuple[int, str]]:
        """Kino kodiga qarab kinoni topish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT message_id, channel_id FROM movies WHERE code = ?",
                (code,)
            )
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                return result  # (message_id, channel_id)
            return None
        except Exception as e:
            print(f"Kino topishda xatolik: {e}")
            return None
    
    def get_stats(self) -> dict:
        """Bot statistikasi uchun kengaytirilgan ma'lumotlar"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Kino statistikasi
            cursor.execute("SELECT COUNT(*) FROM movies")
            total_movies = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM movies WHERE added_date >= datetime('now', '-1 day')")
            movies_last_day = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM movies WHERE added_date >= datetime('now', '-7 day')")
            movies_last_week = cursor.fetchone()[0]
            cursor.execute("""
                SELECT movie_name, code, added_date
                FROM movies
                ORDER BY added_date DESC
                LIMIT 1
            """)
            last_movie_row = cursor.fetchone()

            # Foydalanuvchi statistikasi
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

            # Admin va tizim statistikasi
            cursor.execute("SELECT COUNT(*) FROM admins")
            total_admins = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM subscription_channels")
            subscription_channels = cursor.fetchone()[0]

            conn.close()

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
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Eng katta kod qiymatini topish
            cursor.execute("SELECT code FROM movies WHERE code GLOB '[0-9]*' ORDER BY CAST(code AS INTEGER) DESC LIMIT 1")
            result = cursor.fetchone()
            
            conn.close()
            
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
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM movies WHERE code = ?", (code,))
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception as e:
            print(f"Kod tekshirishda xatolik: {e}")
            return False
    
    def get_subscription_status(self) -> bool:
        """Majburiy obuna holatini olish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT is_enabled FROM subscription_settings WHERE id = 1")
            result = cursor.fetchone()
            conn.close()
            return bool(result[0]) if result else False
        except Exception as e:
            print(f"Obuna holatini olishda xatolik: {e}")
            return False

    def get_start_message(self) -> str:
        """Foydalanuvchilarga yuboriladigan /start xabarini olish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_messages WHERE key = 'start_message'")
            result = cursor.fetchone()
            conn.close()
            if result and result[0]:
                return result[0]
            return DEFAULT_START_MESSAGE
        except Exception as e:
            print(f"/start xabarini olishda xatolik: {e}")
            return DEFAULT_START_MESSAGE

    def update_start_message(self, message: str) -> bool:
        """/start xabarini yangilash"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO bot_messages (key, value) VALUES ('start_message', ?)",
                (message,)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"/start xabarini yangilashda xatolik: {e}")
            return False
    
    def set_subscription_status(self, is_enabled: bool) -> bool:
        """Majburiy obuna holatini o'zgartirish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE subscription_settings SET is_enabled = ? WHERE id = 1", (1 if is_enabled else 0,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Obuna holatini o'zgartirishda xatolik: {e}")
            return False
    
    def add_subscription_channel(self, channel_id: str, channel_name: str = None, channel_username: str = None) -> bool:
        """Majburiy obuna kanalini qo'shish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO subscription_channels (channel_id, channel_name, channel_username) VALUES (?, ?, ?)",
                (channel_id, channel_name, channel_username)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Kanal qo'shishda xatolik: {e}")
            return False
    
    def get_subscription_channels(self) -> list:
        """Majburiy obuna kanallarini olish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id, channel_name, channel_username FROM subscription_channels")
            results = cursor.fetchall()
            conn.close()
            return results
        except Exception as e:
            print(f"Kanallarni olishda xatolik: {e}")
            return []

    def get_subscription_channels_with_ids(self) -> list:
        """Majburiy obuna kanallarini (row id bilan) olish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, channel_id, channel_name, channel_username FROM subscription_channels")
            results = cursor.fetchall()
            conn.close()
            return results
        except Exception as e:
            print(f"Kanallarni olishda xatolik (id bilan): {e}")
            return []
    
    def delete_subscription_channel(self, channel_id: str) -> bool:
        """Majburiy obuna kanalini o'chirish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscription_channels WHERE channel_id = ?", (channel_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Kanalni o'chirishda xatolik: {e}")
            return False

    def delete_subscription_channel_by_id(self, row_id: int) -> bool:
        """Majburiy obuna kanalini row id orqali o'chirish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscription_channels WHERE id = ?", (row_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Kanalni o'chirishda xatolik (id): {e}")
            return False
    
    def get_subscription_message(self) -> str:
        """Obuna xabarini olish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT subscription_message FROM subscription_settings WHERE id = 1")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:"
        except Exception as e:
            print(f"Obuna xabarini olishda xatolik: {e}")
            return "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:"
    
    def update_subscription_message(self, message: str) -> bool:
        """Obuna xabarini yangilash"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE subscription_settings SET subscription_message = ? WHERE id = 1", (message,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Obuna xabarini yangilashda xatolik: {e}")
            return False
    
    # Kanal tugmasi metodlari
    def get_channel_button(self) -> dict:
        """Kanal tugmasi sozlamalarini olish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT is_enabled, button_text, button_url FROM channel_button WHERE id = 1")
            result = cursor.fetchone()
            conn.close()
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
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT is_enabled FROM channel_button WHERE id = 1")
            current = cursor.fetchone()[0]
            new_value = 0 if current else 1
            cursor.execute("UPDATE channel_button SET is_enabled = ? WHERE id = 1", (new_value,))
            conn.commit()
            conn.close()
            return bool(new_value)
        except Exception as e:
            print(f"Kanal tugmasini o'zgartirishda xatolik: {e}")
            return False
    
    def update_channel_button(self, button_text: str = None, button_url: str = None) -> bool:
        """Kanal tugmasini yangilash"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if button_text and button_url:
                cursor.execute("UPDATE channel_button SET button_text = ?, button_url = ? WHERE id = 1", (button_text, button_url))
            elif button_text:
                cursor.execute("UPDATE channel_button SET button_text = ? WHERE id = 1", (button_text,))
            elif button_url:
                cursor.execute("UPDATE channel_button SET button_url = ? WHERE id = 1", (button_url,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Kanal tugmasini yangilashda xatolik: {e}")
            return False
            return "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:"
    
    def set_subscription_message(self, message: str) -> bool:
        """Obuna xabarini o'zgartirish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE subscription_settings SET subscription_message = ? WHERE id = 1", (message,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Obuna xabarini o'zgartirishda xatolik: {e}")
            return False

    def upsert_user(self, user_id: int, first_name: str = None, username: str = None, language_code: str = None) -> None:
        """Foydalanuvchini bazaga qo'shish yoki yangilash"""
        try:
            conn = self.get_connection()
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
            conn.close()
        except Exception as e:
            print(f"Foydalanuvchini saqlashda xatolik: {e}")

    def get_all_users(self) -> List[int]:
        """Broadcast uchun barcha foydalanuvchi ID larini olish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            rows = cursor.fetchall()
            conn.close()
            return [row[0] for row in rows]
        except Exception as e:
            print(f"Foydalanuvchilarni olishda xatolik: {e}")
            return []

    # Admin boshqaruvi metodlari
    def is_admin_user(self, user_id: int) -> bool:
        if user_id == ADMIN_ID:
            return True
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            print(f"Admin tekshirishda xatolik: {e}")
            return False

    def get_admins(self) -> List[Dict]:
        try:
            conn = self.get_connection()
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
            conn.close()
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
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO admins (user_id, first_name, username)
                VALUES (?, ?, ?)
            ''', (user_id, first_name, username))
            conn.commit()
            conn.close()
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
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            return deleted
        except Exception as e:
            print(f"Adminni o'chirishda xatolik: {e}")
            return False

    def get_admin(self, user_id: int) -> Optional[Dict]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, first_name, username,
                       can_manage_movies, can_manage_channels,
                       can_broadcast, can_manage_admins,
                       can_manage_premium
                FROM admins WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            conn.close()
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
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(f"UPDATE admins SET {', '.join(fields)} WHERE user_id = ?", values)
            conn.commit()
            updated = cursor.rowcount > 0
            conn.close()
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
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT {column} FROM admins WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            return bool(row[0]) if row else False
        except Exception as e:
            print(f"Huquq tekshirishda xatolik: {e}")
            return False

    # Premium obuna metodlari
    def get_premium_settings(self) -> Dict:
        try:
            conn = self.get_connection()
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
            conn.close()
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
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE premium_settings
                SET price_1m = ?, price_3m = ?, price_6m = ?, price_12m = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            ''', (price_1m, price_3m, price_6m, price_12m))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Premium narxlarini yangilashda xatolik: {e}")
            return False

    def update_premium_description(self, description: str) -> bool:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE premium_settings
                SET description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            ''', (description.strip(),))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Premium tavsifini yangilashda xatolik: {e}")
            return False

    def toggle_premium_status(self) -> Optional[bool]:
        try:
            conn = self.get_connection()
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
            conn.close()
            return bool(new_value)
        except Exception as e:
            print(f"Premium holatini o'zgartirishda xatolik: {e}")
            return None

    def update_premium_card(self, card_info: str) -> bool:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE premium_settings
                SET card_info = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            ''', (card_info.strip(),))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Karta ma'lumotlarini yangilashda xatolik: {e}")
            return False

    def get_premium_stats(self) -> Dict:
        try:
            conn = self.get_connection()
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
            conn.close()
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
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, first_name, username, plan, expires_at, joined_at
                FROM premium_users
                ORDER BY joined_at DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            conn.close()
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
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, amount, duration, payment_method, reference, created_at
                FROM premium_payments
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            conn.close()
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
            conn = self.get_connection()
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
            conn.close()
            return request_id
        except Exception as e:
            print(f"Premium so'rovini yaratishda xatolik: {e}")
            return None

    def get_premium_request(self, request_id: int) -> Optional[Dict]:
        try:
            conn = self.get_connection()
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
            conn.close()
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
            conn = self.get_connection()
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
            conn.close()
            return updated
        except Exception as e:
            print(f"Premium so'rov holatini yangilashda xatolik: {e}")
            return False


