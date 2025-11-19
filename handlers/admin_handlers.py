import html
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from database import DatabaseManager
from config import ADMIN_ID

class AdminHandlers:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def is_admin(self, user_id: int) -> bool:
        return self.db.is_admin_user(user_id)

    def has_permission(self, user_id: int, permission: str) -> bool:
        return self.db.user_has_permission(user_id, permission)
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return
        # Admin panel /start komandasi orqali ko'rsatiladi, shu sababli /admin buyruqida javob yuborilmaydi
        return
    
    async def set_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Baza kanalini sozlash"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return
        if not self.has_permission(update.effective_user.id, 'channels'):
            await update.message.reply_text("❌ Kanal boshqaruvi huquqi yo'q!")
            return
        
        if len(context.args) == 0:
            await update.message.reply_text(
                "❌ Kanal ID yoki username kiriting!\n\n"
                "Misol:\n"
                "/setchannel -1001234567890\n"
                "yoki\n"
                "/setchannel @channelname"
            )
            return
        
        channel_id = context.args[0]
        
        try:
            chat = await context.bot.get_chat(channel_id)
            
            # Botning kanalda admin ekanligini tekshirish
            bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
            
            if not bot_member.can_post_messages:
                await update.message.reply_text(
                    "❌ Bot kanalda admin emas yoki xabar yuborish huquqi yo'q!\n"
                    "Botni kanalga admin qilib qo'shing va qayta urinib ko'ring."
                )
                return
            
            # Kanalni bazaga saqlash
            if self.db.set_channel(channel_id):
                await update.message.reply_text(
                    f"✅ Baza kanal muvaffaqiyatli sozlandi!\n\n"
                    f"📢 Kanal: {chat.title}\n"
                    f"🆔 ID: <code>{channel_id}</code>",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text("❌ Kanalni saqlashda xatolik!")
        
        except Exception as e:
            await update.message.reply_text(
                f"❌ Xatolik yuz berdi!\n\n"
                f"Sabab: {str(e)}\n\n"
                f"Tekshiring:\n"
                f"1. Kanal ID to'g'ri kiritilganligini\n"
                f"2. Bot kanalda admin ekanligini\n"
                f"3. Bot xabar yuborish huquqiga ega ekanligini"
            )
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Statistika"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return
        
        stats = self.db.get_stats()
        premium = stats.get('premium', {})
        last_movie = stats.get('last_movie', {})

        def format_time(value: str) -> str:
            if not value:
                return ""
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d.%m %H:%M")
            except ValueError:
                return value

        text = "📊 <b>Statistika</b>\n\n"

        text += "🎬 <b>Kino ma'lumotlari</b>\n"
        text += f"• Jami kinolar: {stats['total_movies']}\n"
        text += f"• 24 soatda qo'shilgan: {stats.get('movies_last_24h', 0)}\n"
        text += f"• 7 kunda qo'shilgan: {stats.get('movies_last_7d', 0)}\n"
        if last_movie.get('code'):
            movie_name = last_movie.get('name') or "Noma'lum"
            movie_time = format_time(last_movie.get('added_date'))
            time_part = f" — {movie_time}" if movie_time else ""
            text += f"• Oxirgi kino: {movie_name} (<code>{last_movie['code']}</code>) {time_part}\n"

        text += "\n👥 <b>Foydalanuvchilar</b>\n"
        text += f"• Jami foydalanuvchilar: {stats.get('total_users', 0)}\n"
        text += f"• Yangi (24 soat): {stats.get('users_last_24h', 0)}\n"
        text += f"• Yangi (7 kun): {stats.get('users_last_7d', 0)}\n"
        text += f"• Faol (24 soat): {stats.get('active_users_24h', 0)}\n"
        text += f"• Faol (7 kun): {stats.get('active_users_7d', 0)}\n"

        text += "\n💎 <b>Premium</b>\n"
        text += f"• Premium foydalanuvchilar: {premium.get('active_users', 0)} / {premium.get('total_users', 0)}\n"
        text += f"• Qayd etilgan to'lovlar: {premium.get('total_payments', 0)}\n"

        text += "\n⚙️ <b>Tizim</b>\n"
        text += f"• Adminlar: {stats.get('total_admins', 0)}\n"
        text += f"• Majburiy obuna kanallari: {stats.get('subscription_channels', 0)}\n"
        base_channel = stats.get('base_channel')
        if base_channel:
            text += f"• Baza kanal: <code>{base_channel}</code>\n"
        else:
            text += "• Baza kanal: ❌ Sozlanmagan\n"
        
        await update.message.reply_text(text, parse_mode='HTML')

    def _build_bot_settings_overview(self):
        subscription_enabled = self.db.get_subscription_status()
        subscription_status = "Yoqilgan ✅" if subscription_enabled else "O'chirilgan ❌"
        base_channel = self.db.get_channel()
        base_channel_text = f"<code>{base_channel}</code>" if base_channel else "❌ Sozlanmagan"

        button_settings = self.db.get_channel_button()
        button_status = "Faol ✅" if button_settings.get('is_enabled') else "O'chirilgan ❌"
        button_caption = button_settings.get('button_text') or '—'

        premium_settings = self.db.get_premium_settings()
        premium_status = "Faol 🟢" if premium_settings.get('is_active') else "O'chirilgan 🔴"
        card_info = premium_settings.get('card_info') or "Kiritilmagan"

        text = (
            "⚙️ <b>Bot sozlamalari</b>\n\n"
            f"🔒 Majburiy obuna: {subscription_status}\n"
            f"🗄 Baza kanal: {base_channel_text}\n"
            f"📎 Kanal tugmasi: {button_status} ( {button_caption} )\n"
            f"💎 Premium: {premium_status}\n"
            f"💳 To'lov karta: {card_info}"
        )

        keyboard = [
            [InlineKeyboardButton("📝 /start xabarini tahrirlash", callback_data="botset_edit_start")],
            [InlineKeyboardButton("💾 Database backup", callback_data="botset_backup")],
            [InlineKeyboardButton("🔄 Botni qayta ishga tushirish", callback_data="botset_restart")]
        ]
        return text, InlineKeyboardMarkup(keyboard)

    async def bot_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Botning hozirgi sozlamalari haqida ma'lumot"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return

        text, reply_markup = self._build_bot_settings_overview()
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)

    async def _render_bot_settings_overview(self, query):
        text, reply_markup = self._build_bot_settings_overview()
        try:
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
        except BadRequest as exc:
            if 'message is not modified' in str(exc).lower():
                return
            raise

    async def bot_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id if query.from_user else None
        if not user_id or not self.is_admin(user_id):
            await query.answer("❌ Sizda admin huquqi yo'q!", show_alert=True)
            return

        data = query.data
        if data == "botset_edit_start":
            context.user_data['awaiting_start_message'] = True
            current_message = (self.db.get_start_message() or '').strip()
            preview = html.escape(current_message[:1000]) if current_message else "—"
            text = (
                "📝 <b>/start xabarini tahrirlash</b>\n\n"
                "Quyidagi xabar foydalanuvchilarga /start bosilganda yuboriladi.\n"
                "Yangi matnni matn ko'rinishida yuboring. HTML teglardan foydalanish mumkin.\n\n"
                f"Joriy xabar:\n<pre>{preview}</pre>\n"
                "Mavjud o'zgaruvchilar:\n"
                "• {first_name} – foydalanuvchi ismi\n"
                "• {last_name} – foydalanuvchi familiyasi\n"
                "• {full_name} – to'liq ism\n"
                "• {username} – @username\n"
                "• {user_id} – foydalanuvchi ID\n"
                "• {premium_hint} – Premium bo'limi yoqilgan bo'lsa chiqadigan matn\n\n"
                "Yangi matnni yuboring yoki bekor qiling."
            )
            keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="botset_cancel")]]
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            await query.answer("Yangi matnni yuboring", show_alert=False)
            return
        elif data == "botset_backup":
            user_id = query.from_user.id
            if user_id != ADMIN_ID:
                await query.answer("❌ Ushbu funksiya faqat super admin uchun!", show_alert=True)
                return
            
            await query.answer("Database yuklanmoqda...", show_alert=False)
            
            db_path = self.db.get_db_path()
            if not os.path.exists(db_path):
                await query.message.reply_text("❌ Database fayli topilmadi!")
                return
            
            try:
                filename = os.path.basename(db_path)
                caption = (
                    "📦 <b>Database nusxasi</b>\n\n"
                    "Serverni almashtirishdan oldin ushbu faylni saqlab qo'ying."
                )
                with open(db_path, 'rb') as db_file:
                    await query.message.reply_document(
                        document=db_file,
                        filename=filename,
                        caption=caption,
                        parse_mode='HTML'
                    )
            except Exception as exc:
                await query.message.reply_text(f"❌ Xatolik: {exc}")
            return
        elif data == "botset_restart":
            user_id = query.from_user.id
            if user_id != ADMIN_ID:
                await query.answer("❌ Ushbu funksiya faqat super admin uchun!", show_alert=True)
                return
            
            await query.answer("Bot qayta ishga tushirilmoqda...", show_alert=True)
            
            try:
                await query.message.reply_text("🔄 Bot qayta ishga tushirilmoqda...\nBir necha soniya kuting.")
                import sys
                os.execl(sys.executable, sys.executable, *sys.argv)
            except Exception as exc:
                await query.message.reply_text(f"❌ Xatolik: {exc}")
            return
        elif data == "botset_cancel":
            context.user_data['awaiting_start_message'] = False
            await query.answer("Bekor qilindi", show_alert=True)
            await self._render_bot_settings_overview(query)
            return

        await query.answer()

    async def backup_database(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Super admin uchun database faylini yuklab olish komandasi"""
        if not update.message:
            return

        user_id = update.effective_user.id if update.effective_user else None
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ Ushbu buyruq faqat super admin uchun mavjud!")
            return

        db_path = self.db.get_db_path()
        if not os.path.exists(db_path):
            await update.message.reply_text("❌ Database fayli topilmadi!")
            return

        try:
            filename = os.path.basename(db_path)
            caption = (
                "📦 <b>Database nusxasi</b>\n\n"
                "Serverni almashtirishdan oldin ushbu faylni saqlab qo'ying."
            )
            with open(db_path, 'rb') as db_file:
                await update.message.reply_document(
                    document=db_file,
                    filename=filename,
                    caption=caption,
                    parse_mode='HTML'
                )
        except Exception as exc:
            await update.message.reply_text(f"❌ Nusxa olishda xatolik: {exc}")
    
    async def channel_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kanal boshqaruvi"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return
        
        if not self.has_permission(update.effective_user.id, 'channels'):
            await update.message.reply_text("❌ Kanal boshqaruvi huquqi yo'q!")
            return
        # Majburiy obuna holati
        is_enabled = self.db.get_subscription_status()
        subscription_status = "Yoqilgan ✅" if is_enabled else "O'chirilgan ❌"
        
        # Kanallar soni
        channels = self.db.get_subscription_channels()
        channels_count = len(channels)
        
        text = f"📺 <b>Kanal boshqaruvi</b>\n\n"
        text += f"🔒 Majburiy obuna: {subscription_status}\n\n"
        
        if channels_count == 0:
            text += f"Hech qanday majburiy obuna kanali yo'q.\n\n"
        else:
            text += f"Kanallar soni: {channels_count}\n\n"
        
        text += f"Amalni tanlang:"
        
        # Inline keyboard
        toggle_button_text = "❌ Obunani o'chirish" if is_enabled else "✅ Obunani yoqish"
        
        # Baza kanal
        base_channel = self.db.get_channel()
        base_channel_text = "✅ Sozlangan" if base_channel else "❌ Sozlanmagan"
        
        keyboard = [
            [
                InlineKeyboardButton(toggle_button_text, callback_data="channel_toggle_sub"),
                InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="channel_list")
            ],
            [
                InlineKeyboardButton("➕ Kanal qo'shish", callback_data="channel_add"),
                InlineKeyboardButton("🗑 Kanal o'chirish", callback_data="channel_delete")
            ],
            [
                InlineKeyboardButton("📝 Obuna xabarini tahrirlash", callback_data="channel_edit_message")
            ],
            [
                InlineKeyboardButton(f"🗄 Baza kanal ({base_channel_text})", callback_data="channel_set_base")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)
    
    async def channel_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kanal boshqaruvi callback handler"""
        query = update.callback_query
        
        if not self.is_admin(query.from_user.id) or not self.has_permission(query.from_user.id, 'channels'):
            await query.answer("❌ Kanal boshqaruvi huquqi yo'q!", show_alert=True)
            return
        
        data = query.data
        
        if data == "channel_toggle_sub":
            # Majburiy obunani yoqish/o'chirish
            current_status = self.db.get_subscription_status()
            new_status = not current_status
            
            if self.db.set_subscription_status(new_status):
                status_text = "yoqildi ✅" if new_status else "o'chirildi ❌"
                await query.answer(f"Majburiy obuna {status_text}", show_alert=True)
                
                # Xabarni yangilash
                is_enabled = new_status
                subscription_status = "Yoqilgan ✅" if is_enabled else "O'chirilgan ❌"
                channels = self.db.get_subscription_channels()
                channels_count = len(channels)
                
                text = f"📺 <b>Kanal boshqaruvi</b>\n\n"
                text += f"🔒 Majburiy obuna: {subscription_status}\n\n"
                
                if channels_count == 0:
                    text += f"Hech qanday majburiy obuna kanali yo'q.\n\n"
                else:
                    text += f"Kanallar soni: {channels_count}\n\n"
                
                text += f"Amalni tanlang:"
                
                toggle_button_text = "❌ Obunani o'chirish" if is_enabled else "✅ Obunani yoqish"
                
                # Baza kanal
                base_channel = self.db.get_channel()
                base_channel_text = "✅ Sozlangan" if base_channel else "❌ Sozlanmagan"
                
                keyboard = [
                    [
                        InlineKeyboardButton(toggle_button_text, callback_data="channel_toggle_sub"),
                        InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="channel_list")
                    ],
                    [
                        InlineKeyboardButton("➕ Kanal qo'shish", callback_data="channel_add"),
                        InlineKeyboardButton("🗑 Kanal o'chirish", callback_data="channel_delete")
                    ],
                    [
                        InlineKeyboardButton("📝 Obuna xabarini tahrirlash", callback_data="channel_edit_message")
                    ],
                    [
                        InlineKeyboardButton(f"🗄 Baza kanal ({base_channel_text})", callback_data="channel_set_base")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
            else:
                await query.answer("❌ Xatolik yuz berdi!", show_alert=True)
        
        elif data == "channel_list":
            channels = self.db.get_subscription_channels()
            
            if len(channels) == 0:
                text = "📋 <b>Kanallar ro'yxati</b>\n\n❌ Hech qanday kanal sozlanmagan"
            else:
                text = "📋 <b>Kanallar ro'yxati</b>\n\n"
                for i, (channel_id, channel_name, channel_username) in enumerate(channels, 1):
                    name = channel_name or channel_username or channel_id
                    text += f"{i}. {name}\n   ID: <code>{channel_id}</code>\n\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="channel_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
            await query.answer()
        
        elif data == "channel_add":
            # Kanal qo'shish holatini saqlash
            context.user_data['awaiting_channel'] = True
            
            text = "📡 <b>Yangi kanal qo'shish</b>\n\n"
            text += "Kanal havolasini yuboring yoki kanal postini forward qiling.\n\n"
            text += "Misol: @channelname yoki -1001234567890"
            
            keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="channel_cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.answer("Kanal havolasini yoki postini yuboring", show_alert=False)
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
        
        elif data == "channel_delete":
            channels = self.db.get_subscription_channels()
            
            if len(channels) == 0:
                await query.answer("O'chirish uchun kanallar yo'q", show_alert=True)
            else:
                text = "🗑 <b>Kanal o'chirish</b>\n\n"
                text += "O'chirish uchun kanalni tanlang:"
                
                keyboard = []
                for channel_id, channel_name, channel_username in channels:
                    name = channel_name or channel_username or channel_id
                    keyboard.append([InlineKeyboardButton(f"🗑 {name}", callback_data=f"channel_delete_{channel_id}")])
                
                keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="channel_back")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
                await query.answer()
        
        elif data.startswith("channel_delete_"):
            # Kanalni o'chirish
            channel_id = data.replace("channel_delete_", "")
            
            if self.db.delete_subscription_channel(channel_id):
                await query.answer("Kanal muvaffaqiyatli o'chirildi ✅", show_alert=True)
                
                # Kanal o'chirish sahifasiga qaytish
                channels = self.db.get_subscription_channels()
                
                if len(channels) == 0:
                    # Agar kanallar qolmasa, bosh menyuga qaytish
                    await self.show_channel_management_menu(query)
                else:
                    text = "🗑 <b>Kanal o'chirish</b>\n\n"
                    text += "O'chirish uchun kanalni tanlang:"
                    
                    keyboard = []
                    for ch_id, ch_name, ch_username in channels:
                        name = ch_name or ch_username or ch_id
                        keyboard.append([InlineKeyboardButton(f"🗑 {name}", callback_data=f"channel_delete_{ch_id}")])
                    
                    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="channel_back")])
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
            else:
                await query.answer("❌ Kanalni o'chirishda xatolik!", show_alert=True)
        
        elif data == "channel_edit_message":
            # Obuna xabarini tahrirlash
            context.user_data['awaiting_sub_message'] = True
            
            current_message = self.db.get_subscription_message()
            
            text = "📝 <b>Obuna xabarini tahrirlash</b>\n\n"
            text += f"Joriy xabar:\n<i>{current_message}</i>\n\n"
            text += "Yangi xabarni yuboring:"
            
            keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="channel_cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.answer()
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
        
        elif data == "channel_set_base":
            # Baza kanal tanlash
            context.user_data['awaiting_base_channel'] = True
            
            current_channel = self.db.get_channel()
            
            text = "🗄 <b>Baza kanal sozlash</b>\n\n"
            
            if current_channel:
                text += f"Joriy baza kanal: <code>{current_channel}</code>\n\n"
            
            text += "Bu kanal kinolar saqlanadigan maxfiy kanal hisoblanadi.\n\n"
            text += "Kanal havolasini yuboring yoki kanal postini forward qiling.\n\n"
            text += "Misol: @channelname yoki -1001234567890"
            
            keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="channel_cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.answer()
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
        
        elif data == "channel_cancel":
            # Barcha kutish holatlarini bekor qilish
            context.user_data['awaiting_channel'] = False
            context.user_data['awaiting_sub_message'] = False
            context.user_data['awaiting_base_channel'] = False
            
            await query.answer("Bekor qilindi", show_alert=True)
            await self.show_channel_management_menu(query)
        
        elif data == "channel_back":
            # Bosh menyuga qaytish
            await self.show_channel_management_menu(query)
            await query.answer()
    
    async def show_channel_management_menu(self, query):
        """Kanal boshqaruvi asosiy menyusini ko'rsatish"""
        is_enabled = self.db.get_subscription_status()
        subscription_status = "Yoqilgan ✅" if is_enabled else "O'chirilgan ❌"
        channels = self.db.get_subscription_channels()
        channels_count = len(channels)
        
        text = f"📺 <b>Kanal boshqaruvi</b>\n\n"
        text += f"🔒 Majburiy obuna: {subscription_status}\n\n"
        
        if channels_count == 0:
            text += f"Hech qanday majburiy obuna kanali yo'q.\n\n"
        else:
            text += f"Kanallar soni: {channels_count}\n\n"
        
        text += f"Amalni tanlang:"
        
        toggle_button_text = "❌ Obunani o'chirish" if is_enabled else "✅ Obunani yoqish"
        
        # Baza kanal
        base_channel = self.db.get_channel()
        base_channel_text = "✅ Sozlangan" if base_channel else "❌ Sozlanmagan"
        
        keyboard = [
            [
                InlineKeyboardButton(toggle_button_text, callback_data="channel_toggle_sub"),
                InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="channel_list")
            ],
            [
                InlineKeyboardButton("➕ Kanal qo'shish", callback_data="channel_add"),
                InlineKeyboardButton("🗑 Kanal o'chirish", callback_data="channel_delete")
            ],
            [
                InlineKeyboardButton("📝 Obuna xabarini tahrirlash", callback_data="channel_edit_message")
            ],
            [
                InlineKeyboardButton(f"🗄 Baza kanal ({base_channel_text})", callback_data="channel_set_base")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)

    def _build_admin_overview(self):
        admins = self.db.get_admins()
        text = "👑 <b>Admin boshqaruvi</b>\n\n"
        text += f"Jami adminlar: {len(admins)}\n\n"
        if admins:
            for idx, admin in enumerate(admins, 1):
                name = admin['first_name'] or 'Noma\'lum'
                if admin['username']:
                    name += f" (@{admin['username']})"
                if admin['user_id'] == ADMIN_ID:
                    name += " — Super Admin"
                rights = []
                if admin['can_manage_movies']:
                    rights.append('🎬')
                if admin['can_manage_channels']:
                    rights.append('📺')
                if admin['can_broadcast']:
                    rights.append('📢')
                if admin['can_manage_admins']:
                    rights.append('👑')
                if admin.get('can_manage_premium'):
                    rights.append('💎')
                rights_text = ''.join(rights) if rights else '—'
                text += (
                    f"{idx}. {name}\n"
                    f"   ID: <code>{admin['user_id']}</code>\n"
                    f"   Huquqlar: {rights_text}\n\n"
                )
        else:
            text += "Hozircha qo'shimcha adminlar yo'q."
        keyboard = [
            [InlineKeyboardButton("➕ Admin qo'shish", callback_data="admin_add"), InlineKeyboardButton("🗑 Admin o'chirish", callback_data="admin_delete")],
            [InlineKeyboardButton("⚙️ Huquqlar", callback_data="admin_permissions"), InlineKeyboardButton("🔄 Yangilash", callback_data="admin_refresh")]
        ]
        return text, InlineKeyboardMarkup(keyboard)

    async def admin_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
            return
        if not self.has_permission(update.effective_user.id, 'admins'):
            await update.message.reply_text("❌ Adminlarni boshqarish huquqi yo'q!")
            return
        text, reply_markup = self._build_admin_overview()
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)

    async def admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        if not self.is_admin(user_id) or not self.has_permission(user_id, 'admins'):
            await query.answer("❌ Admin boshqaruvi uchun huquq yetarli emas!", show_alert=True)
            return
        data = query.data
        if data == "admin_refresh":
            await query.answer("Yangilandi ✅", show_alert=False)
            await self._render_admin_overview(query)
            return
        if data == "admin_add":
            context.user_data['awaiting_admin_add'] = True
            text = (
                "➕ <b>Admin qo'shish</b>\n\n"
                "Yangi adminni qo'shish uchun foydalanuvchining xabarini forward qiling\n"
                "yoki ID/username ni yuboring.\n\n"
                "Masalan: <code>123456789</code> yoki <code>@username</code>"
            )
            keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="admin_cancel")]]
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            await query.answer("Yangi admin ma'lumotini yuboring", show_alert=False)
            return
        if data == "admin_cancel":
            context.user_data['awaiting_admin_add'] = False
            await query.answer("Bekor qilindi", show_alert=True)
            await self._render_admin_overview(query)
            return
        if data == "admin_delete":
            admins = [a for a in self.db.get_admins() if a['user_id'] != ADMIN_ID]
            if not admins:
                await query.answer("O'chirish uchun admin topilmadi", show_alert=True)
                return
            keyboard = []
            for admin in admins:
                label = admin['first_name'] or str(admin['user_id'])
                if admin['username']:
                    label += f" (@{admin['username']})"
                keyboard.append([InlineKeyboardButton(f"🗑 {label}", callback_data=f"admin_remove_{admin['user_id']}")])
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_refresh")])
            text = "🗑 <b>Admin o'chirish</b>\n\nO'chirish uchun adminni tanlang:"
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            await query.answer()
            return
        if data.startswith("admin_remove_"):
            target_id = int(data.replace("admin_remove_", ""))
            if target_id == ADMIN_ID:
                await query.answer("Asosiy adminni o'chirish mumkin emas!", show_alert=True)
                return
            if self.db.remove_admin_user(target_id):
                await query.answer("Admin o'chirildi ✅", show_alert=True)
            else:
                await query.answer("Adminni o'chirishda xatolik", show_alert=True)
            await self._render_admin_overview(query)
            return
        if data == "admin_permissions":
            admins = [a for a in self.db.get_admins() if a['user_id'] != ADMIN_ID]
            if not admins:
                await query.answer("Huquqlarni sozlash uchun admin yo'q", show_alert=True)
                return
            keyboard = []
            for admin in admins:
                name = admin['first_name'] or str(admin['user_id'])
                if admin['username']:
                    name += f" (@{admin['username']})"
                keyboard.append([InlineKeyboardButton(name, callback_data=f"admin_perm_{admin['user_id']}")])
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_refresh")])
            text = "⚙️ <b>Huquqlarni sozlash</b>\n\nAdminni tanlang:"
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            await query.answer()
            return
        if data.startswith("admin_perm_"):
            target_id = int(data.replace("admin_perm_", ""))
            admin = self.db.get_admin(target_id)
            if not admin:
                await query.answer("Admin topilmadi", show_alert=True)
                await self._render_admin_overview(query)
                return
            await self._show_admin_permissions(query, admin)
            await query.answer()
            return
        if data.startswith("admin_toggle_"):
            try:
                _, _, perm_key, user_part = data.split('_', 3)
                target_id = int(user_part)
            except ValueError:
                await query.answer()
                return
            admin = self.db.get_admin(target_id)
            if not admin:
                await query.answer("Admin topilmadi", show_alert=True)
                await self._render_admin_overview(query)
                return
            perm_map = {
                'movies': 'can_manage_movies',
                'channels': 'can_manage_channels',
                'broadcast': 'can_broadcast',
                'admins': 'can_manage_admins',
                'premium': 'can_manage_premium'
            }
            column = perm_map.get(perm_key)
            if not column:
                await query.answer()
                return
            new_value = not admin[column]
            success = self.db.update_admin_permissions(target_id, **{column: new_value})
            if success:
                await query.answer("Huquq yangilandi", show_alert=False)
            else:
                await query.answer("Huquqni yangilab bo'lmadi", show_alert=True)
            admin = self.db.get_admin(target_id)
            await self._show_admin_permissions(query, admin)
            return
        await query.answer()

    async def _render_admin_overview(self, query):
        text, reply_markup = self._build_admin_overview()
        try:
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
        except BadRequest as exc:
            if 'message is not modified' in str(exc).lower():
                return
            raise

    async def _show_admin_permissions(self, query, admin: dict):
        if not admin:
            await self._render_admin_overview(query)
            return
        rights = {
            'movies': ('🎬 Kino boshqaruvi', admin['can_manage_movies']),
            'channels': ('📺 Kanal boshqaruvi', admin['can_manage_channels']),
            'broadcast': ('📢 Xabar yuborish', admin['can_broadcast']),
            'admins': ('👑 Admin boshqaruvi', admin['can_manage_admins']),
            'premium': ('💎 Premium boshqaruvi', admin.get('can_manage_premium', False))
        }
        admin_name = admin.get('first_name') or "Noma'lum"
        text = (
            "⚙️ <b>Huquqlar</b>\n\n"
            f"Admin: {admin_name}\n"
            f"ID: <code>{admin['user_id']}</code>\n"
        )
        keyboard = []
        for key, (label, value) in rights.items():
            status = "✅" if value else "❌"
            keyboard.append([
                InlineKeyboardButton(f"{label}: {status}", callback_data=f"admin_toggle_{key}_{admin['user_id']}")
            ])
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_permissions")])
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
