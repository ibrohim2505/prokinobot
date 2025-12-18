from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import DatabaseManager
import random
import string

class MovieHandlers:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def generate_code(self, length: int = 8) -> str:
        """Tasodifiy kod generatsiya qilish"""
        characters = string.ascii_uppercase + string.digits
        return ''.join(random.choice(characters) for _ in range(length))
    
    def is_admin(self, user_id: int) -> bool:
        return self.db.is_admin_user(user_id)

    def can_manage_movies(self, user_id: int) -> bool:
        return self.db.user_has_permission(user_id, 'movies')

    async def _get_unsubscribed_channels(self, bot, user_id: int):
        if self.db.is_admin_user(user_id):
            return []
        if not self.db.get_subscription_status():
            return []
        channels = self.db.get_subscription_channels()
        if not channels:
            return []

        unsubscribed = []
        for channel_id, channel_name, channel_username in channels:
            # Instagram yoki boshqa tashqi havolalarda majburiy obuna tekshirilmaydi
            if isinstance(channel_id, str) and "instagram.com" in channel_id.lower():
                continue

            chat_id = channel_id
            if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
                try:
                    chat_id = int(chat_id)
                except ValueError:
                    pass
            try:
                member = await bot.get_chat_member(chat_id, user_id)
                status = getattr(member, 'status', '')
                is_member = getattr(member, 'is_member', True)
                if status in ('left', 'kicked') or (status == 'restricted' and not is_member):
                    unsubscribed.append((channel_id, channel_name, channel_username))
            except Exception:
                unsubscribed.append((channel_id, channel_name, channel_username))
        return unsubscribed

    async def _ensure_subscription(self, update: Update, context: ContextTypes.DEFAULT_TYPE, code: str) -> bool:
        """Majburiy obuna talablarini tekshirish"""
        unsubscribed = await self._get_unsubscribed_channels(context.bot, update.effective_user.id)
        if not unsubscribed:
            return True

        text_lines = [self.db.get_subscription_message().strip()]

        # Instagram kabi tashqi havolalarni informatsion tarzda ko'rsatish
        all_channels = self.db.get_subscription_channels()
        external_links = [cid for cid, _, _ in all_channels if isinstance(cid, str) and "instagram.com" in cid.lower()]
        if external_links:
            text_lines.append("\n📎 Instagram profil(lar)i (tekshirilmaydi):")
            for link in external_links:
                text_lines.append(f"• {link}")

        buttons = []
        for _, channel_name, channel_username in unsubscribed:
            if channel_username:
                username = channel_username.lstrip('@')
                buttons.append([InlineKeyboardButton("➕ Kanalga obuna bo'lish", url=f"https://t.me/{username}")])

        verify_data = f"verify_sub:{code}"
        buttons.append([InlineKeyboardButton("✅ Obunani tekshirish", callback_data=verify_data)])

        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text('\n'.join(text_lines), parse_mode='HTML', reply_markup=reply_markup)
        context.user_data['pending_movie_code'] = code
        return False

    async def _deliver_movie(self, chat_id: int, code: str, context: ContextTypes.DEFAULT_TYPE):
        movie_data = self.db.get_movie(code)
        if not movie_data:
            return False, "❌ Kino topilmadi!\nIltimos, kodni to'g'ri kiriting."

        message_id, channel_id = movie_data
        button_settings = self.db.get_channel_button()
        reply_markup = None
        if button_settings.get('is_enabled'):
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                button_settings['button_text'], url=button_settings['button_url']
            )]])

        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=channel_id,
                message_id=message_id,
                reply_markup=reply_markup
            )
        except Exception as e:
            return False, f"❌ Kinoni yuborishda xatolik!\n\nSabab: {str(e)}"

        return True, None
    
    async def add_movie(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin tomonidan kino qo'shish"""
        if not self.can_manage_movies(update.effective_user.id):
            return
        
        # Baza kanal sozlanganligini tekshirish
        channel_id = self.db.get_channel()
        if not channel_id:
            await update.message.reply_text(
                "❌ Baza kanal sozlanmagan!\n"
                "Avval /setchannel buyrug'i bilan baza kanalini sozlang."
            )
            return
        
        # Kino ma'lumotlarini olish
        message = update.message
        
        # Faqat video, hujjat yoki audio qabul qilish
        if not (message.video or message.document or message.audio):
            await update.message.reply_text(
                "❌ Iltimos, kino faylini yuboring!\n"
                "Video, hujjat yoki audio formatida bo'lishi kerak."
            )
            return
        
        # Noyob kod generatsiya qilish
        code = self.generate_code()
        
        # Kino nomini olish
        movie_name = None
        if message.video and message.video.file_name:
            movie_name = message.video.file_name
        elif message.document and message.document.file_name:
            movie_name = message.document.file_name
        elif message.caption:
            movie_name = message.caption
        
        try:
            # Kinoni baza kanalga yuborish
            if message.video:
                sent_message = await context.bot.send_video(
                    chat_id=channel_id,
                    video=message.video.file_id,
                    caption=f"🎬 Kod: {code}\n{message.caption if message.caption else ''}",
                    supports_streaming=True
                )
            elif message.document:
                sent_message = await context.bot.send_document(
                    chat_id=channel_id,
                    document=message.document.file_id,
                    caption=f"🎬 Kod: {code}\n{message.caption if message.caption else ''}"
                )
            elif message.audio:
                sent_message = await context.bot.send_audio(
                    chat_id=channel_id,
                    audio=message.audio.file_id,
                    caption=f"🎬 Kod: {code}\n{message.caption if message.caption else ''}"
                )
            
            # Kinoni bazaga saqlash
            if self.db.add_movie(code, sent_message.message_id, channel_id, movie_name):
                await update.message.reply_text(
                    f"✅ Kino muvaffaqiyatli qo'shildi!\n\n"
                    f"🎬 Kino kodi: <code>{code}</code>\n"
                    f"📢 Kanal: <code>{channel_id}</code>\n"
                    f"🆔 Message ID: {sent_message.message_id}",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text("❌ Kinoni bazaga saqlashda xatolik!")
        
        except Exception as e:
            await update.message.reply_text(
                f"❌ Xatolik yuz berdi!\n\n"
                f"Sabab: {str(e)}\n\n"
                f"Tekshiring:\n"
                f"1. Bot baza kanalda admin ekanligini\n"
                f"2. Bot xabar yuborish huquqiga ega ekanligini"
            )
    
    async def get_movie(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Foydalanuvchi kino kodini yuboradi"""
        message = update.message
        code = message.text.strip()
        
        # Kodning formatini tekshirish (faqat raqam va 1-10000 oralig'i)
        if not code.isdigit():
            await update.message.reply_text(
                "❌ Kod faqat raqamlardan iborat bo'lishi kerak!\n"
                "Masalan: 1, 21, 137, 2024"
            )
            return
        
        code_num = int(code)
        if code_num < 1 or code_num > 10000:
            await update.message.reply_text(
                "❌ Kod 1 dan 10000 gacha bo'lishi kerak!"
            )
            return

        # Majburiy obuna tekshiruvi
        is_allowed = await self._ensure_subscription(update, context, code)
        if not is_allowed:
            return
        
        delivered, error_text = await self._deliver_movie(update.effective_chat.id, code, context)
        if not delivered and error_text:
            await update.message.reply_text(error_text)

    async def verify_subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data or ""
        code = data.split(':', 1)[1] if ':' in data else context.user_data.get('pending_movie_code')

        unsubscribed = await self._get_unsubscribed_channels(context.bot, user_id)
        if unsubscribed:
            await query.answer("⚠️ Kanallarga obuna bo'lmadingiz", show_alert=True)
            return

        if not code:
            await query.answer("❌ Kino kodi topilmadi", show_alert=True)
            return

        delivered, error_text = await self._deliver_movie(query.message.chat_id, code, context)
        if delivered:
            await query.answer("✅ Obuna tasdiqlandi", show_alert=False)
            context.user_data.pop('pending_movie_code', None)
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            await query.answer("❌ Kino topilmadi", show_alert=True)
            if error_text:
                await context.bot.send_message(query.message.chat_id, error_text)

