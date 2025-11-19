from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import DatabaseManager

class MovieAdminHandlers:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def is_admin(self, user_id: int) -> bool:
        return self.db.is_admin_user(user_id)

    def has_movie_permission(self, user_id: int) -> bool:
        return self.db.user_has_permission(user_id, 'movies')
    
    async def movie_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kino boshqaruvi"""
        if not self.has_movie_permission(update.effective_user.id):
            await update.message.reply_text("❌ Sizda kino boshqaruvi huquqi yo'q!")
            return
        
        stats = self.db.get_stats()
        base_channel = self.db.get_channel()
        
        text = f"🎬 <b>Kino boshqaruvi</b>\n\n"
        text += f"📊 Jami kinolar: {stats['total_movies']}\n"
        
        if base_channel:
            text += f"📢 Baza kanal: <code>{base_channel}</code>\n\n"
        else:
            text += "📢 Baza kanal: ❌ Sozlanmagan\n\n"
        
        text += "Amalni tanlang:"
        
        keyboard = [
            [
                InlineKeyboardButton("📋 Kinolar ro'yxati", callback_data="movie_list"),
                InlineKeyboardButton("➕ Kino qo'shish", callback_data="movie_add")
            ],
            [
                InlineKeyboardButton("🗑 Kino o'chirish", callback_data="movie_delete"),
                InlineKeyboardButton("🔍 Kino qidirish", callback_data="movie_search")
            ],
            [
                InlineKeyboardButton("🔘 Kanal tugmasi", callback_data="movie_channel_button")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)
    
    async def movie_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kino boshqaruvi callback handler"""
        query = update.callback_query
        
        if not self.has_movie_permission(query.from_user.id):
            await query.answer("❌ Sizda kino boshqaruvi huquqi yo'q!", show_alert=True)
            return
        
        data = query.data
        
        if data == "movie_list":
            # Kinolar ro'yxati
            stats = self.db.get_stats()
            
            if stats['total_movies'] == 0:
                text = "📋 <b>Kinolar ro'yxati</b>\n\n❌ Hech qanday kino qo'shilmagan"
            else:
                # Oxirgi 10 ta kinoni ko'rsatish
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT code, movie_name, added_date FROM movies ORDER BY id DESC LIMIT 10")
                movies = cursor.fetchall()
                conn.close()
                
                text = f"📋 <b>Kinolar ro'yxati</b>\n\n"
                text += f"Jami kinolar: {stats['total_movies']}\n\n"
                text += "Oxirgi 10 ta kino:\n\n"
                
                for i, (code, name, date) in enumerate(movies, 1):
                    movie_name = name if name else "Noma'lum"
                    text += f"{i}. <code>{code}</code> - {movie_name}\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="movie_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
            await query.answer()
        
        elif data == "movie_add":
            # Kino qo'shish
            base_channel = self.db.get_channel()
            
            if not base_channel:
                await query.answer("❌ Avval baza kanalini sozlang!", show_alert=True)
                return
            
            context.user_data['awaiting_movie_step'] = 1  # Bosqich 1: Video
            context.user_data['movie_data'] = {}
            
            text = "➕ <b>Kino qo'shish (1/4)</b>\n\n"
            text += "📹 Kino video faylini yuboring."
            
            keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="movie_cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.answer("Video faylini yuboring", show_alert=False)
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
        
        elif data == "movie_delete":
            # Kino o'chirish
            context.user_data['awaiting_movie_code_delete'] = True
            
            text = "🗑 <b>Kino o'chirish</b>\n\n"
            text += "O'chirmoqchi bo'lgan kino kodini yuboring.\n\n"
            text += "Masalan: <code>ABC12345</code>"
            
            keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="movie_cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.answer("Kino kodini yuboring", show_alert=False)
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
        
        elif data == "movie_search":
            # Kino qidirish
            context.user_data['awaiting_movie_code_search'] = True
            
            text = "🔍 <b>Kino qidirish</b>\n\n"
            text += "Qidirmoqchi bo'lgan kino kodini yuboring.\n\n"
            text += "Masalan: <code>ABC12345</code>"
            
            keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="movie_cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.answer("Kino kodini yuboring", show_alert=False)
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
        
        elif data == "movie_cancel":
            # Barcha kutish holatlarini bekor qilish
            context.user_data['awaiting_movie'] = False
            context.user_data['awaiting_movie_step'] = 0
            context.user_data['movie_data'] = {}
            context.user_data['awaiting_movie_code_delete'] = False
            context.user_data['awaiting_movie_code_search'] = False
            
            await query.answer("Bekor qilindi", show_alert=True)
            await self.show_movie_management_menu(query)
        
        elif data == "movie_back":
            # Bosh menyuga qaytish
            await self.show_movie_management_menu(query)
            await query.answer()
        
        elif data == "movie_channel_button":
            # Kanal tugmasi sozlamalari
            await self.show_channel_button_menu(query)
            await query.answer()
        
        elif data == "btn_toggle":
            # Tugmani yoqish/o'chirish
            new_status = self.db.toggle_channel_button()
            status_text = "yoqildi" if new_status else "o'chirildi"
            await query.answer(f"✅ Kanal tugmasi {status_text}!", show_alert=True)
            await self.show_channel_button_menu(query)
        
        elif data == "btn_edit_text":
            # Tugma matnini tahrirlash
            context.user_data['awaiting_button_text'] = True
            
            text = "✏️ <b>Tugma matnini tahrirlash</b>\n\n"
            text += "Yangi tugma matnini yuboring.\n\n"
            text += "Masalan: 📢 Kanalimiz, 🎬 Filmlar kanali"
            
            keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="btn_cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
            await query.answer()
        
        elif data == "btn_edit_url":
            # Tugma linkini tahrirlash
            context.user_data['awaiting_button_url'] = True
            
            text = "🔗 <b>Tugma linkini tahrirlash</b>\n\n"
            text += "Yangi kanal linkini yuboring.\n\n"
            text += "Masalan: https://t.me/your_channel"
            
            keyboard = [[InlineKeyboardButton("❌ Bekor qilish", callback_data="btn_cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
            await query.answer()
        
        elif data == "btn_cancel":
            # Bekor qilish
            context.user_data['awaiting_button_text'] = False
            context.user_data['awaiting_button_url'] = False
            await query.answer("Bekor qilindi")
            await self.show_channel_button_menu(query)
        
        elif data == "btn_back":
            # Kino boshqaruviga qaytish
            await self.show_movie_management_menu(query)
            await query.answer()
    
    async def show_channel_button_menu(self, query):
        """Kanal tugmasi sozlamalari menyusi"""
        button_settings = self.db.get_channel_button()
        
        status = "✅ Yoqilgan" if button_settings['is_enabled'] else "❌ O'chirilgan"
        toggle_text = "🔴 O'chirish" if button_settings['is_enabled'] else "🟢 Yoqish"
        
        text = f"🔘 <b>Kanal tugmasi sozlamalari</b>\n\n"
        text += f"📊 Holat: {status}\n"
        text += f"📝 Tugma matni: {button_settings['button_text']}\n"
        text += f"🔗 Link: {button_settings['button_url']}\n\n"
        text += "Amalni tanlang:"
        
        keyboard = [
            [InlineKeyboardButton(toggle_text, callback_data="btn_toggle")],
            [
                InlineKeyboardButton("✏️ Matnni tahrirlash", callback_data="btn_edit_text"),
                InlineKeyboardButton("🔗 Linkni tahrirlash", callback_data="btn_edit_url")
            ],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="btn_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
    
    async def show_movie_management_menu(self, query):
        """Kino boshqaruvi asosiy menyusini ko'rsatish"""
        stats = self.db.get_stats()
        base_channel = self.db.get_channel()
        
        text = f"🎬 <b>Kino boshqaruvi</b>\n\n"
        text += f"📊 Jami kinolar: {stats['total_movies']}\n"
        
        if base_channel:
            text += f"📢 Baza kanal: <code>{base_channel}</code>\n\n"
        else:
            text += "📢 Baza kanal: ❌ Sozlanmagan\n\n"
        
        text += "Amalni tanlang:"
        
        keyboard = [
            [
                InlineKeyboardButton("📋 Kinolar ro'yxati", callback_data="movie_list"),
                InlineKeyboardButton("➕ Kino qo'shish", callback_data="movie_add")
            ],
            [
                InlineKeyboardButton("🗑 Kino o'chirish", callback_data="movie_delete"),
                InlineKeyboardButton("🔍 Kino qidirish", callback_data="movie_search")
            ],
            [
                InlineKeyboardButton("🔘 Kanal tugmasi", callback_data="movie_channel_button")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
