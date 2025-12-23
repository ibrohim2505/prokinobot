#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from typing import Optional, Tuple
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

from config import BOT_TOKEN, ADMIN_ID
from database import DatabaseManager
from handlers import AdminHandlers, MovieHandlers, MovieAdminHandlers, PremiumHandlers

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database
db = DatabaseManager('database/movies.db')

# Handlers
admin_handlers = AdminHandlers(db)
movie_handlers = MovieHandlers(db)
movie_admin_handlers = MovieAdminHandlers(db)
premium_handlers = PremiumHandlers(db)

PREMIUM_BUTTON_TEXT = "💎 Premium obuna"
BOT_SETTINGS_BUTTON_TEXT = "⚙️ Bot sozlamlari"
PREMIUM_PLAN_LABELS = {1: "1 oy", 3: "3 oy", 6: "6 oy", 12: "12 oy"}
PREMIUM_PRICE_KEYS = {1: 'price_1m', 3: 'price_3m', 6: 'price_6m', 12: 'price_12m'}
PREMIUM_FLOW_KEY = "premium_flow"

def register_user(update: Update):
    """Foydalanuvchini bazaga saqlash"""
    user = update.effective_user
    if not user:
        return
    try:
        db.upsert_user(
            user_id=user.id,
            first_name=user.first_name,
            username=user.username,
            language_code=user.language_code
        )
    except Exception as e:
        logger.error(f"Foydalanuvchini saqlashda xatolik: {e}")


def _format_amount(amount):
    if amount is None:
        return "—"
    return f"{amount:,}".replace(',', ' ') + " so'm"


def build_premium_info_text(settings: dict) -> Optional[str]:
    if not settings or not settings.get('is_active'):
        return None

    parts = ["💎 <b>Premium obuna</b>"]
    description = (settings.get('description') or '').strip()
    if description:
        parts.append(description)

    parts.append('\n'.join([
        f"• 1 oy: {_format_amount(settings.get('price_1m'))}",
        f"• 3 oy: {_format_amount(settings.get('price_3m'))}",
        f"• 6 oy: {_format_amount(settings.get('price_6m'))}",
        f"• 12 oy: {_format_amount(settings.get('price_12m'))}"
    ]))

    card_info = (settings.get('card_info') or '').strip()
    if card_info:
        parts.append(f"💳 To'lov uchun karta: {card_info}")

    parts.append("To'lovni amalga oshirgach, chekni adminlarga yuboring.")
    return '\n\n'.join(parts)


def build_user_keyboard(premium_active: bool):
    if premium_active:
        return ReplyKeyboardMarkup([[KeyboardButton(PREMIUM_BUTTON_TEXT)]], resize_keyboard=True)
    return ReplyKeyboardRemove()


def _get_plan_price(settings: dict, duration: int) -> Optional[int]:
    key = PREMIUM_PRICE_KEYS.get(duration)
    if not key:
        return None
    return settings.get(key)


def build_premium_intro_text(settings: dict) -> str:
    description = (settings.get('description') or '').strip()
    parts = ["💎 <b>Premium obuna tariflari</b>"]
    if description:
        parts.append(description)
    parts.append("Quyidagi tariflardan birini tanlang:")
    return '\n\n'.join(parts)


def build_premium_plan_keyboard(settings: dict) -> InlineKeyboardMarkup:
    rows = []
    for duration in (1, 3, 6, 12):
        label = PREMIUM_PLAN_LABELS.get(duration, f"{duration} oy")
        price = _format_amount(_get_plan_price(settings, duration))
        rows.append([
            InlineKeyboardButton(
                f"{label} - {price}",
                callback_data=f"userprem:plan:{duration}"
            )
        ])
    rows.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="userprem:cancel:0")])
    return InlineKeyboardMarkup(rows)


def build_plan_detail_text(duration: int, amount: Optional[int]) -> str:
    label = PREMIUM_PLAN_LABELS.get(duration, f"{duration} oy")
    return (
        f"💳 <b>{label} tarifi</b>\n\n"
        f"Narx: {_format_amount(amount)}\n\n"
        "Davom etish uchun \"Tasdiqlash\" tugmasini bosing."
    )


def build_payment_instruction_text(duration: int, amount: Optional[int], settings: dict) -> str:
    label = PREMIUM_PLAN_LABELS.get(duration, f"{duration} oy")
    card_info = (settings.get('card_info') or "Admin bilan bog'laning.").strip()
    return (
        "✅ <b>Tarif tasdiqlandi</b>\n\n"
        f"Tarif: {label}\n"
        f"Summa: {_format_amount(amount)}\n"
        f"💳 To'lov uchun karta: {card_info}\n\n"
        "To'lovni amalga oshirgach, chekni PDF yoki skrinshot ko'rinishida shu chatga yuboring.\n"
        "Chek yuborilgach, admin tasdiqlashini kuting."
    )


def set_premium_flow_state(context: ContextTypes.DEFAULT_TYPE, state: str, **data):
    flow = context.user_data.get(PREMIUM_FLOW_KEY, {})
    flow.update(data)
    flow['state'] = state
    context.user_data[PREMIUM_FLOW_KEY] = flow


def clear_premium_flow(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop(PREMIUM_FLOW_KEY, None)


def render_start_message(template: str, user, premium_active: bool) -> str:
    premium_hint = ""
    if premium_active:
        premium_hint = (
            "💎 Premium kontentga ega bo'lish uchun "
            "<b>\"💎 Premium obuna\"</b> tugmasidan foydalaning."
        )

    full_name = ' '.join(filter(None, [user.first_name, user.last_name])).strip()
    if not full_name:
        full_name = user.first_name or (user.username and f"@{user.username}") or ""

    replacements = {
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "full_name": full_name,
        "username": f"@{user.username}" if user.username else "",
        "user_id": str(user.id) if getattr(user, 'id', None) else "",
        "premium_hint": premium_hint
    }

    text = template
    for key, value in replacements.items():
        text = text.replace(f"{{{key}}}", value)
    return text

def build_admin_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    rows = []
    stats_row = [KeyboardButton("📊 Statistika")]
    if db.user_has_permission(user_id, 'channels'):
        stats_row.append(KeyboardButton("📺 Kanal boshqaruvi"))
    rows.append(stats_row)
    action_row = []
    if db.user_has_permission(user_id, 'movies'):
        action_row.append(KeyboardButton("🎬 Kino boshqaruvi"))
    if db.user_has_permission(user_id, 'broadcast'):
        action_row.append(KeyboardButton("📢 Xabar yuborish"))
    if action_row:
        rows.append(action_row)
    premium_admin_row = []
    if db.user_has_permission(user_id, 'premium'):
        premium_admin_row.append(KeyboardButton(PREMIUM_BUTTON_TEXT))
    if db.user_has_permission(user_id, 'admins'):
        premium_admin_row.append(KeyboardButton("👑 Admin boshqaruvi"))
    if premium_admin_row:
        rows.append(premium_admin_row)
    rows.append([KeyboardButton(BOT_SETTINGS_BUTTON_TEXT)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def build_button_markup(buttons: list):
    """Tugmalar ro'yxatidan InlineKeyboard yaratish"""
    if not buttons:
        return None
    keyboard = []
    for button in buttons:
        keyboard.append([InlineKeyboardButton(button['text'], url=button['url'])])
    return InlineKeyboardMarkup(keyboard)

async def send_broadcast_preview(bot, chat_id: int, broadcast_data: dict):
    """Admin uchun xabar previewini yuborish"""
    reply_markup = build_button_markup(broadcast_data.get('buttons'))
    content_type = broadcast_data.get('content_type')
    text = broadcast_data.get('text')
    file_id = broadcast_data.get('file_id')
    if content_type == 'photo':
        await bot.send_photo(chat_id=chat_id, photo=file_id, caption=text, parse_mode='HTML', reply_markup=reply_markup)
    elif content_type == 'video':
        await bot.send_video(chat_id=chat_id, video=file_id, caption=text, parse_mode='HTML', supports_streaming=True, reply_markup=reply_markup)
    elif content_type == 'document':
        await bot.send_document(chat_id=chat_id, document=file_id, caption=text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=reply_markup)

def clear_broadcast_state(context: ContextTypes.DEFAULT_TYPE):
    """Broadcast holatini tozalash"""
    context.user_data.pop('broadcast_state', None)
    context.user_data.pop('broadcast_data', None)

def parse_buttons_input(text: str) -> list:
    """Matndan tugmalar ro'yxatini ajratib olish"""
    buttons = []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if len(lines) > 5:
        raise ValueError("Bir vaqtda eng ko'pi bilan 5 ta tugma qo'shishingiz mumkin")
    for line in lines:
        if '-' not in line:
            raise ValueError("Har bir qatorda 'Matn - https://link' formatidan foydalaning")
        label, url = line.split('-', 1)
        label = label.strip()
        url = url.strip()
        if not label or not url:
            raise ValueError("Matn yoki link bo'sh bo'lishi mumkin emas")
        if not (url.startswith('http://') or url.startswith('https://') or url.startswith('tg://')):
            raise ValueError("Link http://, https:// yoki tg:// bilan boshlanishi kerak")
        if len(label) > 64:
            raise ValueError("Tugma matni 64 ta belgidan oshmasligi kerak")
        buttons.append({'text': label, 'url': url})
    return buttons

async def broadcast_to_all_users(bot, broadcast_data: dict):
    """Xabarni barcha foydalanuvchilarga yuborish"""
    users = db.get_all_users()
    success = 0
    failed = 0
    reply_markup = build_button_markup(broadcast_data.get('buttons'))
    content_type = broadcast_data.get('content_type')
    text = broadcast_data.get('text')
    file_id = broadcast_data.get('file_id')
    for user_id in users:
        try:
            if content_type == 'photo':
                await bot.send_photo(chat_id=user_id, photo=file_id, caption=text, parse_mode='HTML', reply_markup=reply_markup)
            elif content_type == 'video':
                await bot.send_video(chat_id=user_id, video=file_id, caption=text, parse_mode='HTML', supports_streaming=True, reply_markup=reply_markup)
            elif content_type == 'document':
                await bot.send_document(chat_id=user_id, document=file_id, caption=text, parse_mode='HTML', reply_markup=reply_markup)
            else:
                await bot.send_message(chat_id=user_id, text=text, parse_mode='HTML', reply_markup=reply_markup)
            success += 1
        except Exception as e:
            logger.warning(f"Broadcast yuborishda xatolik (user {user_id}): {e}")
            failed += 1
    total = len(users)
    return success, failed, total

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start buyrug'i"""
    user = update.effective_user
    register_user(update)
    
    if db.is_admin_user(user.id):
        reply_markup = build_admin_keyboard(user.id)
        
        text = (
            f"👑 <b>Admin Panel</b>\n\n"
            f"Kerakli bo'limni tanlang:"
        )
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        premium_settings = db.get_premium_settings()
        premium_active = bool(premium_settings.get('is_active'))
        template = db.get_start_message()
        text = render_start_message(template, user, premium_active)
        reply_markup = build_user_keyboard(premium_active)
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help buyrug'i"""
    user = update.effective_user
    register_user(update)
    
    if db.is_admin_user(user.id):
        text = (
            f"❓ <b>Yordam</b>\n\n"
            f"♻️ <b>Admin Buyruqlari:</b>\n"
            f"/start - Botni ishga tushirish\n"
            f"/admin - Admin panel\n"
            f"/setchannel - Baza kanalini sozlash\n"
            f"/stats - Statistika\n"
            f"/help - Yordam\n\n"
            f"📝 Kino qo'shish uchun kinoni botga yuboring"
        )
    else:
        text = (
            f"❓ <b>Yordam</b>\n\n"
            f"Kinoni olish uchun kino kodini yuboring.\n"
            f"Kod faqat raqamlardan iborat va 1 dan 10000 gacha bo'lishi kerak.\n"
            f"Masalan: <code>1</code>, <code>21</code>, <code>137</code>, <code>5000</code>"
        )
    
    await update.message.reply_text(text, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha xabarlarni qayta ishlash"""
    register_user(update)
    user_id = update.effective_user.id
    message_text = update.message.text if update.message.text else ""
    caption_text = update.message.caption if update.message.caption else ""
    is_admin = db.is_admin_user(user_id)
    movie_permission = db.user_has_permission(user_id, 'movies') if is_admin else False
    channel_permission = db.user_has_permission(user_id, 'channels') if is_admin else False
    broadcast_permission = db.user_has_permission(user_id, 'broadcast') if is_admin else False
    admin_permission = db.user_has_permission(user_id, 'admins') if is_admin else False
    premium_permission = db.user_has_permission(user_id, 'premium') if is_admin else False
    
    # Database restore qabul qilish
    if context.user_data.get('awaiting_restore_db'):
        if user_id != ADMIN_ID:
            context.user_data['awaiting_restore_db'] = False
            await update.message.reply_text("❌ Ushbu funksiya faqat super admin uchun!")
            return
        
        if update.message.document:
            doc = update.message.document
            if not doc.file_name.endswith('.db'):
                await update.message.reply_text("❌ Faqat .db formatidagi fayllar qabul qilinadi!")
                return
            
            try:
                # Faylni yuklab olish
                db_path = db.get_db_path()
                if db_path == "PostgreSQL (Railway)":
                    await update.message.reply_text("❌ PostgreSQL ishlatilmoqda. SQLite restore qilish mumkin emas.")
                    context.user_data['awaiting_restore_db'] = False
                    return
                
                await update.message.reply_text("⏳ Database tiklanmoqda...")
                
                file = await context.bot.get_file(doc.file_id)
                await file.download_to_drive(db_path)
                
                await update.message.reply_text(
                    "✅ Database muvaffaqiyatli tiklandi!\n\n"
                    "⚠️ Bot qayta ishga tushirilishi kerak.\n"
                    "Yangi ma'lumotlar faqat bot qayta ishga tushgandan keyin ko'rinadi."
                )
                context.user_data['awaiting_restore_db'] = False
            except Exception as e:
                await update.message.reply_text(f"❌ Xatolik: {str(e)}")
        else:
            await update.message.reply_text("❌ Iltimos, .db faylini yuboring!")
        return
    
    # Admin tugmalarni qayta ishlash
    if is_admin:
        if context.user_data.get('premium_state'):
            handled_premium = await premium_handlers.handle_state_message(update, context)
            if handled_premium:
                return
        if context.user_data.get('awaiting_admin_add'):
            if not admin_permission:
                await update.message.reply_text("❌ Admin qo'shish huquqi yo'q!")
                context.user_data['awaiting_admin_add'] = False
                return
            target_user = None
            if update.message.forward_from and not update.message.forward_from.is_bot:
                target_user = update.message.forward_from
            elif message_text:
                candidate = message_text.strip()
                if candidate.startswith('@'):
                    try:
                        target_user = await context.bot.get_chat(candidate)
                    except Exception:
                        target_user = None
                elif candidate.lstrip('-').isdigit():
                    try:
                        target_user = await context.bot.get_chat(int(candidate))
                    except Exception:
                        target_user = None
            if not target_user:
                await update.message.reply_text(
                    "❌ Foydalanuvchi topilmadi. Xabarni forward qiling yoki ID/username yuboring."
                )
                return
            if getattr(target_user, 'type', 'private') != 'private':
                await update.message.reply_text("❌ Faqat shaxsiy (private) foydalanuvchilarni admin qilishingiz mumkin!")
                return
            if target_user.id == update.effective_user.id:
                await update.message.reply_text("❌ O'zingizni admin sifatida qayta qo'sha olmaysiz!")
                return
            if target_user.is_bot:
                await update.message.reply_text("❌ Botlarni admin sifatida qo'shib bo'lmaydi!")
                return
            if db.is_admin_user(target_user.id):
                await update.message.reply_text("❗️ Bu foydalanuvchi allaqachon admin")
                return
            if db.add_admin_user(target_user.id, target_user.first_name, getattr(target_user, 'username', None)):
                context.user_data['awaiting_admin_add'] = False
                await update.message.reply_text(
                    f"✅ Yangi admin qo'shildi!\nID: <code>{target_user.id}</code>",
                    parse_mode='HTML'
                )
                await admin_handlers.admin_management(update, context)
            else:
                await update.message.reply_text("❌ Adminni qo'shishda xatolik yuz berdi!")
            return
        if context.user_data.get('broadcast_state') and not broadcast_permission:
            await update.message.reply_text("❌ Xabar yuborish huquqi olib tashlangan.")
            clear_broadcast_state(context)
            return
        broadcast_state = context.user_data.get('broadcast_state')
        if broadcast_permission and broadcast_state == 'awaiting_content':
            content_type = None
            file_id = None
            text_content = caption_text
            if update.message.photo:
                content_type = 'photo'
                file_id = update.message.photo[-1].file_id
            elif update.message.video:
                content_type = 'video'
                file_id = update.message.video.file_id
            elif update.message.document:
                content_type = 'document'
                file_id = update.message.document.file_id
            elif message_text:
                content_type = 'text'
                text_content = message_text
            
            if not content_type:
                await update.message.reply_text(
                    "❌ Iltimos, matn, rasm yoki video yuboring!"
                )
                return
            
            if not text_content.strip():
                await update.message.reply_text(
                    "❌ Xabarga matn (caption) kiriting. Rasm/video uchun izoh yozing."
                )
                return
            
            context.user_data['broadcast_data'] = {
                'content_type': content_type,
                'file_id': file_id,
                'text': text_content.strip(),
                'buttons': []
            }
            context.user_data['broadcast_state'] = 'awaiting_buttons'
            await update.message.reply_text(
                "✅ Xabar qabul qilindi! Endi tugmalarni kiriting.\n\n"
                "Har bir qatorda: <code>Matn - https://link</code> formatida yozing.\n"
                "Tugmalar kerak bo'lmasa, <b>skip</b> deb yozing.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="broadcast_cancel")]])
            )
            return
        elif broadcast_permission and broadcast_state == 'awaiting_buttons':
            if not message_text:
                await update.message.reply_text(
                    "❌ Tugma ma'lumotini matn ko'rinishida yuboring yoki 'skip' deb yozing."
                )
                return
            buttons_text = message_text.strip()
            if buttons_text.lower() in ['skip', 'o\'tkazish', 'yoq', "yo'q"]:
                buttons = []
            else:
                try:
                    buttons = parse_buttons_input(buttons_text)
                except ValueError as e:
                    await update.message.reply_text(f"❌ {str(e)}")
                    return
            broadcast_data = context.user_data.get('broadcast_data', {})
            broadcast_data['buttons'] = buttons
            context.user_data['broadcast_data'] = broadcast_data
            context.user_data['broadcast_state'] = 'ready'
            await send_broadcast_preview(context.bot, update.effective_chat.id, broadcast_data)
            await update.message.reply_text(
                "📢 Xabar yuborishga tayyor. Tugmalardan birini tanlang:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Yuborish", callback_data="broadcast_send")],
                    [InlineKeyboardButton("🔁 Tugmalarni qayta kiritish", callback_data="broadcast_reenter_buttons")],
                    [InlineKeyboardButton("❌ Bekor qilish", callback_data="broadcast_cancel")]
                ])
            )
            return
        elif broadcast_permission and broadcast_state == 'ready':
            await update.message.reply_text(
                "📢 Xabar allaqachon tayyor. '✅ Yuborish' tugmasini bosing yoki '❌ Bekor qilish'ni tanlang."
            )
            return
        elif broadcast_state and not broadcast_permission:
            await update.message.reply_text("❌ Xabar yuborish huquqi yo'q")
            clear_broadcast_state(context)
            return
        # Obuna xabarini tahrirlash
        if context.user_data.get('awaiting_sub_message'):
            if not channel_permission:
                await update.message.reply_text("❌ Kanal sozlamalarini tahrirlash huquqi yo'q!")
                context.user_data['awaiting_sub_message'] = False
                return
            if message_text:
                if db.set_subscription_message(message_text):
                    await update.message.reply_text(
                        f"✅ Obuna xabari muvaffaqiyatli o'zgartirildi!\n\n"
                        f"Yangi xabar:\n<i>{message_text}</i>",
                        parse_mode='HTML'
                    )
                    context.user_data['awaiting_sub_message'] = False
                else:
                    await update.message.reply_text("❌ Xatolik yuz berdi!")
            return

        if context.user_data.get('awaiting_start_message'):
            if not is_admin:
                context.user_data['awaiting_start_message'] = False
                return
            if not message_text:
                await update.message.reply_text("❌ Iltimos, yangi /start xabarini matn ko'rinishida yuboring.")
                return
            new_text = message_text.strip()
            if not new_text:
                await update.message.reply_text("❌ Xabar bo'sh bo'lishi mumkin emas.")
                return
            if db.update_start_message(new_text):
                context.user_data['awaiting_start_message'] = False
                await update.message.reply_text(
                    "✅ /start xabari yangilandi!\n"
                    "Matnda {first_name}, {full_name}, {username}, {user_id} va {premium_hint} kabi o'zgaruvchilardan foydalanishingiz mumkin.",
                    parse_mode='HTML'
                )
                await admin_handlers.bot_settings(update, context)
            else:
                await update.message.reply_text("❌ /start xabarini saqlashda xatolik yuz berdi!")
            return
        
        # Kino qo'shish (bosqichma-bosqich)
        if context.user_data.get('awaiting_movie_step'):
            if not movie_permission:
                context.user_data['awaiting_movie_step'] = 0
                context.user_data['movie_data'] = {}
                await update.message.reply_text("❌ Kino qo'shish huquqi yo'q!")
                return
            step = context.user_data.get('awaiting_movie_step', 0)
            movie_data = context.user_data.get('movie_data', {})
            
            # Bosqich 1: Video fayl
            if step == 1:
                if update.message.video or update.message.document:
                    # Video ma'lumotlarini saqlash
                    if update.message.video:
                        movie_data['video'] = update.message.video.file_id
                        movie_data['duration'] = update.message.video.duration
                    else:
                        movie_data['video'] = update.message.document.file_id
                        movie_data['duration'] = 0
                    
                    context.user_data['movie_data'] = movie_data
                    context.user_data['awaiting_movie_step'] = 2
                    
                    await update.message.reply_text(
                        "✅ Video qabul qilindi!\n\n"
                        "➕ <b>Kino qo'shish (2/4)</b>\n\n"
                        "🎬 Kino nomini kiriting:",
                        parse_mode='HTML'
                    )
                else:
                    await update.message.reply_text("❌ Iltimos, video yoki hujjat faylini yuboring!")
                return
            
            # Bosqich 2: Kino nomi
            elif step == 2:
                if message_text:
                    movie_data['name'] = message_text
                    context.user_data['movie_data'] = movie_data
                    context.user_data['awaiting_movie_step'] = 3
                    
                    await update.message.reply_text(
                        "✅ Kino nomi qabul qilindi!\n\n"
                        "➕ <b>Kino qo'shish (3/4)</b>\n\n"
                        "🎭 Kino janrini kiriting:\n"
                        "Masalan: Komediya, Fantastika, Jangari, Sarguzasht"
                    )
                else:
                    await update.message.reply_text("❌ Iltimos, kino nomini kiriting!")
                return
            
            # Bosqich 3: Janr
            elif step == 3:
                if message_text:
                    movie_data['genre'] = message_text
                    context.user_data['movie_data'] = movie_data
                    context.user_data['awaiting_movie_step'] = 4
                    
                    # Avtomatik keyingi kodini taklif qilish
                    suggested_code = db.get_next_movie_code()
                    
                    await update.message.reply_text(
                        "✅ Janr qabul qilindi!\n\n"
                        "➕ <b>Kino qo'shish (4/4)</b>\n\n"
                        f"🔢 Kino kodini kiriting (faqat raqam):\n"
                        f"Taklif: <code>{suggested_code}</code>\n\n"
                        f"Diapazon: 1 dan 10000 gacha",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("❌ Bekor qilish", callback_data="movie_cancel")
                        ]])
                    )
                else:
                    await update.message.reply_text("❌ Iltimos, janrni kiriting!")
                return
            
            # Bosqich 4: Kod va bazaga saqlash
            elif step == 4:
                if message_text:
                    code = message_text.strip()
                    
                    # Faqat raqam tekshirish
                    if not code.isdigit():
                        await update.message.reply_text(
                            "❌ Kod faqat raqamlardan iborat bo'lishi kerak!\n"
                            "Masalan: 1, 21, 137, 1500\n\n"
                            "Iltimos, faqat raqam kiriting:",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("❌ Bekor qilish", callback_data="movie_cancel")
                            ]])
                        )
                        return
                    
                    code_num = int(code)
                    if code_num < 1 or code_num > 10000:
                        await update.message.reply_text(
                            "❌ Kod 1 dan 10000 gacha bo'lishi kerak!\n\n"
                            "Iltimos, to'g'ri kod kiriting:",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("❌ Bekor qilish", callback_data="movie_cancel")
                            ]])
                        )
                        return
                    
                    # Kod mavjudligini tekshirish
                    if db.is_code_exists(code):
                        suggested_code = db.get_next_movie_code()
                        await update.message.reply_text(
                            f"❌ Bu kod ({code}) allaqachon ishlatilgan!\n\n"
                            f"Taklif: <code>{suggested_code}</code>\n\n"
                            f"Iltimos, boshqa kod kiriting:",
                            parse_mode='HTML',
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("❌ Bekor qilish", callback_data="movie_cancel")
                            ]])
                        )
                        return
                    
                    # Bazaga saqlash
                    channel_id = db.get_channel()
                    
                    if not channel_id:
                        await update.message.reply_text("❌ Baza kanal sozlanmagan!")
                        context.user_data['awaiting_movie_step'] = 0
                        context.user_data['movie_data'] = {}
                        return
                    
                    try:
                        # Video davomiyligini formatlash
                        duration = movie_data.get('duration', 0)
                        if duration > 0:
                            hours = duration // 3600
                            minutes = (duration % 3600) // 60
                            if hours > 0:
                                duration_text = f"{hours} soat {minutes} daqiqa"
                            else:
                                duration_text = f"{minutes} daqiqa"
                        else:
                            duration_text = "Noma'lum"
                        
                        # Caption yaratish
                        caption = f"🎬 <b>{movie_data['name']}</b>\n\n"
                        caption += f"🎭 Janr: {movie_data['genre']}\n"
                        caption += f"⏱ Davomiyligi: {duration_text}\n"
                        caption += f"🔢 Kod: <code>{code}</code>"
                        
                        # Kanal tugmasi sozlamalarini olish
                        button_settings = db.get_channel_button()
                        reply_markup = None
                        
                        if button_settings['is_enabled']:
                            caption += f"\n\n{button_settings['button_text']}"
                            reply_markup = InlineKeyboardMarkup([[
                                InlineKeyboardButton(button_settings['button_text'], url=button_settings['button_url'])
                            ]])
                        
                        # Video ni baza kanalga yuborish
                        sent_message = await context.bot.send_video(
                            chat_id=channel_id,
                            video=movie_data['video'],
                            caption=caption,
                            parse_mode='HTML',
                            supports_streaming=True,
                            reply_markup=reply_markup
                        )
                        
                        # Bazaga saqlash
                        if db.add_movie(code, sent_message.message_id, channel_id, movie_data['name'], movie_data['genre'], duration):
                            await update.message.reply_text(
                                f"✅ Kino muvaffaqiyatli qo'shildi!\n\n"
                                f"🎬 Nomi: {movie_data['name']}\n"
                                f"🎭 Janr: {movie_data['genre']}\n"
                                f"⏱ Davomiyligi: {duration_text}\n"
                                f"🔢 Kod: <code>{code}</code>\n"
                                f"📢 Kanal: <code>{channel_id}</code>\n"
                                f"🆔 Message ID: {sent_message.message_id}",
                                parse_mode='HTML'
                            )
                        else:
                            await update.message.reply_text("❌ Kinoni bazaga saqlashda xatolik!")
                        
                        # Tozalash
                        context.user_data['awaiting_movie_step'] = 0
                        context.user_data['movie_data'] = {}
                    
                    except Exception as e:
                        await update.message.reply_text(
                            f"❌ Xatolik yuz berdi!\n\n"
                            f"Sabab: {str(e)}"
                        )
                        context.user_data['awaiting_movie_step'] = 0
                        context.user_data['movie_data'] = {}
                else:
                    await update.message.reply_text("❌ Iltimos, kodni kiriting!")
                return
        
        # Kino o'chirish
        if context.user_data.get('awaiting_movie_code_delete'):
            if not movie_permission:
                context.user_data['awaiting_movie_code_delete'] = False
                await update.message.reply_text("❌ Kino o'chirish huquqi yo'q!")
                return
            if message_text:
                code = message_text.strip().upper()
                
                # Kinoni bazadan qidirish
                movie_data = db.get_movie(code)
                
                if not movie_data:
                    await update.message.reply_text("❌ Bunday kodli kino topilmadi!")
                    return
                
                # Kinoni o'chirish (faqat bazadan)
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM movies WHERE code = ?", (code,))
                conn.commit()
                conn.close()
                
                await update.message.reply_text(
                    f"✅ Kino muvaffaqiyatli o'chirildi!\n\n"
                    f"Kino kodi: <code>{code}</code>",
                    parse_mode='HTML'
                )
                context.user_data['awaiting_movie_code_delete'] = False
            return
        
        # Kino qidirish
        if context.user_data.get('awaiting_movie_code_search'):
            if not movie_permission:
                context.user_data['awaiting_movie_code_search'] = False
                await update.message.reply_text("❌ Kino qidirish huquqi yo'q!")
                return
            if message_text:
                code = message_text.strip().upper()
                
                # Kinoni bazadan qidirish
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT code, movie_name, channel_id, message_id, added_date FROM movies WHERE code = ?", (code,))
                movie = cursor.fetchone()
                conn.close()
                
                if not movie:
                    await update.message.reply_text("❌ Bunday kodli kino topilmadi!")
                    return
                
                code, name, channel_id, message_id, date = movie
                movie_name = name if name else "Noma'lum"
                
                text = f"🔍 <b>Kino ma'lumotlari</b>\n\n"
                text += f"Kino kodi: <code>{code}</code>\n"
                text += f"Nomi: {movie_name}\n"
                text += f"Kanal ID: <code>{channel_id}</code>\n"
                text += f"Xabar ID: {message_id}\n"
                text += f"Qo'shilgan sana: {date}"
                
                await update.message.reply_text(text, parse_mode='HTML')
                context.user_data['awaiting_movie_code_search'] = False
            return
        
        # Kanal tugmasi matnini tahrirlash
        if context.user_data.get('awaiting_button_text'):
            if not movie_permission:
                context.user_data['awaiting_button_text'] = False
                await update.message.reply_text("❌ Tugmani tahrirlash huquqi yo'q!")
                return
            if message_text:
                if db.update_channel_button(button_text=message_text):
                    await update.message.reply_text(
                        f"✅ Tugma matni o'zgartirildi!\n\n"
                        f"Yangi matn: {message_text}",
                        parse_mode='HTML'
                    )
                    context.user_data['awaiting_button_text'] = False
                else:
                    await update.message.reply_text("❌ Xatolik yuz berdi!")
            return
        
        # Kanal tugmasi linkini tahrirlash
        if context.user_data.get('awaiting_button_url'):
            if not movie_permission:
                context.user_data['awaiting_button_url'] = False
                await update.message.reply_text("❌ Tugma linkini o'zgartirish huquqi yo'q!")
                return
            if message_text:
                # Link formatini tekshirish
                if not message_text.startswith('https://t.me/'):
                    await update.message.reply_text(
                        "❌ Link formati noto'g'ri!\n\n"
                        "Link https://t.me/ bilan boshlanishi kerak.\n"
                        "Masalan: https://t.me/your_channel"
                    )
                    return
                
                if db.update_channel_button(button_url=message_text):
                    await update.message.reply_text(
                        f"✅ Tugma linki o'zgartirildi!\n\n"
                        f"Yangi link: {message_text}",
                        parse_mode='HTML'
                    )
                    context.user_data['awaiting_button_url'] = False
                else:
                    await update.message.reply_text("❌ Xatolik yuz berdi!")
            return
        
        # Baza kanal sozlash
        if context.user_data.get('awaiting_base_channel'):
            if not channel_permission:
                context.user_data['awaiting_base_channel'] = False
                await update.message.reply_text("❌ Baza kanalini sozlash huquqi yo'q!")
                return
            # Forward qilingan xabar
            if update.message.forward_from_chat:
                chat = update.message.forward_from_chat
                channel_id = str(chat.id)
                
                try:
                    # Botning kanalda admin ekanligini tekshirish
                    bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
                    
                    if bot_member.status not in ['administrator', 'creator']:
                        await update.message.reply_text(
                            "❌ Bot bu kanalda admin emas!\n"
                            "Botni kanalga admin qilib qo'shing va qayta urinib ko'ring."
                        )
                        return
                    
                    # Xabar yuborish huquqini tekshirish
                    if hasattr(bot_member, 'can_post_messages') and not bot_member.can_post_messages:
                        await update.message.reply_text(
                            "❌ Bot xabar yuborish huquqiga ega emas!\n"
                            "Botga 'Xabar yuborish' huquqini bering."
                        )
                        return
                    
                    # Kanalni baza kanal sifatida sozlash
                    if db.set_channel(channel_id):
                        await update.message.reply_text(
                            f"✅ Baza kanal muvaffaqiyatli sozlandi!\n\n"
                            f"📺 Kanal: {chat.title}\n"
                            f"🆔 ID: <code>{channel_id}</code>",
                            parse_mode='HTML'
                        )
                        context.user_data['awaiting_base_channel'] = False
                    else:
                        await update.message.reply_text("❌ Xatolik yuz berdi!")
                
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Xatolik yuz berdi!\n\n"
                        f"Sabab: {str(e)}\n\n"
                        f"Tekshiring:\n"
                        f"1. Bot kanalda admin ekanligini\n"
                        f"2. Bot xabar yuborish huquqiga ega ekanligini"
                    )
                return
            
            # Matn sifatida kanal ID, username yoki havola
            elif message_text:
                channel_input = message_text.strip()
                
                # Agar havola bo'lsa, ID yoki username ajratib olish
                if 't.me/' in channel_input or 'telegram.me/' in channel_input:
                    # https://t.me/channelname yoki https://t.me/+code formatida
                    if '/+' in channel_input:
                        # Private link - ishlamaydi
                        await update.message.reply_text(
                            "❌ Private havola ishlamaydi!\n\n"
                            "Kanal postini forward qiling yoki kanal ID ni yuboring.\n\n"
                            "Kanal ID ni olish uchun:\n"
                            "1. Kanal postini @userinfobot ga forward qiling\n"
                            "2. Bot sizga kanal ID ni beradi"
                        )
                        return
                    else:
                        # Public channel - username ajratib olish
                        parts = channel_input.split('/')
                        channel_input = '@' + parts[-1] if not parts[-1].startswith('@') else parts[-1]
                
                try:
                    chat = await context.bot.get_chat(channel_input)
                    
                    # Botning kanalda admin ekanligini tekshirish
                    bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
                    
                    if bot_member.status not in ['administrator', 'creator']:
                        await update.message.reply_text(
                            "❌ Bot bu kanalda admin emas!\n"
                            "Botni kanalga admin qilib qo'shing va qayta urinib ko'ring."
                        )
                        return
                    
                    # Xabar yuborish huquqini tekshirish
                    if hasattr(bot_member, 'can_post_messages') and not bot_member.can_post_messages:
                        await update.message.reply_text(
                            "❌ Bot xabar yuborish huquqiga ega emas!\n"
                            "Botga 'Xabar yuborish' huquqini bering."
                        )
                        return
                    
                    # Kanalni baza kanal sifatida sozlash
                    if db.set_channel(str(chat.id)):
                        await update.message.reply_text(
                            f"✅ Baza kanal muvaffaqiyatli sozlandi!\n\n"
                            f"📺 Kanal: {chat.title}\n"
                            f"🆔 ID: <code>{chat.id}</code>",
                            parse_mode='HTML'
                        )
                        context.user_data['awaiting_base_channel'] = False
                    else:
                        await update.message.reply_text("❌ Xatolik yuz berdi!")
                
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Xatolik yuz berdi!\n\n"
                        f"Sabab: {str(e)}\n\n"
                        f"Agar kanal maxfiy bo'lsa:\n"
                        f"1. Kanal postini forward qiling\n"
                        f"2. Yoki kanal ID ni yuboring (masalan: -1001234567890)\n\n"
                        f"Tekshiring:\n"
                        f"1. Bot kanalda admin ekanligini\n"
                        f"2. Bot xabar yuborish huquqiga ega ekanligini"
                    )
                return
        
        # Havola qo'shish jarayonini tekshirish
        if context.user_data.get('awaiting_link'):
            if not channel_permission:
                context.user_data['awaiting_link'] = False
                await update.message.reply_text("❌ Majburiy obuna kanallarini boshqarish huquqi yo'q!")
                return
            
            # Format: Tugma nomi | https://havola.uz
            if message_text and '|' in message_text:
                try:
                    parts = message_text.split('|', 1)
                    button_text = parts[0].strip()
                    link_url = parts[1].strip()
                    
                    # URL tekshirish
                    if not (link_url.startswith('http://') or link_url.startswith('https://')):
                        await update.message.reply_text(
                            "❌ Havola http:// yoki https:// bilan boshlanishi kerak!\n\n"
                            "Misol: <code>Saytimiz | https://example.com</code>",
                            parse_mode='HTML'
                        )
                        return
                    
                    # Havolani bazaga qo'shish (link turi)
                    if db.add_subscription_channel(link_url, button_text, None, False, 'link'):
                        await update.message.reply_text(
                            f"✅ Havola muvaffaqiyatli qo'shildi!\n\n"
                            f"🔗 Tugma: {button_text}\n"
                            f"🌐 Havola: {link_url}",
                            parse_mode='HTML'
                        )
                        context.user_data['awaiting_link'] = False
                    else:
                        await update.message.reply_text("❌ Havola qo'shishda xatolik yuz berdi!")
                
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Xatolik yuz berdi: {str(e)}\n\n"
                        f"To'g'ri format:\n"
                        f"<code>Tugma nomi | https://havola.uz</code>",
                        parse_mode='HTML'
                    )
            else:
                await update.message.reply_text(
                    "❌ Noto'g'ri format!\n\n"
                    "To'g'ri format:\n"
                    "<code>Tugma nomi | https://havola.uz</code>\n\n"
                    "Misol:\n"
                    "<code>🌐 Saytimiz | https://example.com</code>",
                    parse_mode='HTML'
                )
            return
        
        # Kanal qo'shish jarayonini tekshirish
        if context.user_data.get('awaiting_channel'):
            if not channel_permission:
                context.user_data['awaiting_channel'] = False
                await update.message.reply_text("❌ Majburiy obuna kanallarini boshqarish huquqi yo'q!")
                return
            
            is_required = context.user_data.get('channel_is_required', True)
            channel_type = context.user_data.get('channel_type', 'channel')
            
            # So'rovli kanal uchun - faqat t.me/+ invite link qabul qilish
            if channel_type == 'request':
                if message_text:
                    invite_link = message_text.strip()
                    
                    # t.me/+ yoki telegram.me/+ formatini tekshirish
                    if 't.me/+' in invite_link or 't.me/joinchat/' in invite_link or 'telegram.me/+' in invite_link:
                        # Invite havolasini to'g'ridan-to'g'ri saqlash
                        # Kanal nomi sifatida havolaning oxirgi qismini olamiz
                        link_parts = invite_link.split('/')
                        link_code = link_parts[-1] if link_parts else invite_link
                        
                        if db.add_subscription_channel(invite_link, f"So'rovli kanal ({link_code[:10]}...)", None, is_required, 'request'):
                            await update.message.reply_text(
                                f"✅ So'rovli kanal muvaffaqiyatli qo'shildi!\n\n"
                                f"🔐 Turi: So'rovli kanal\n"
                                f"🔗 Havola: {invite_link}\n\n"
                                f"ℹ️ Foydalanuvchilar ushbu havolaga borib qo'shilish so'rovi yuborishlari kerak.",
                                parse_mode='HTML'
                            )
                            context.user_data['awaiting_channel'] = False
                            context.user_data['channel_is_required'] = True
                            context.user_data['channel_type'] = 'channel'
                        else:
                            await update.message.reply_text("❌ Bu havola allaqachon qo'shilgan yoki xatolik yuz berdi!")
                        return
                    else:
                        await update.message.reply_text(
                            "❌ So'rovli kanal uchun invite havola kerak!\n\n"
                            "Invite havolani qanday olish:\n"
                            "1. Kanalingizga kiring\n"
                            "2. Kanal sozlamalarini oching\n"
                            "3. 'Taklif havolalari' bo'limiga kiring\n"
                            "4. '+' tugmasini bosing va 'So'rov kerak' ni yoqing\n"
                            "5. Yaratilgan havolani nusxalab yuboring\n\n"
                            "Havola formati: https://t.me/+XXXXXXXXX"
                        )
                        return
                # Forward qilingan xabardan ham invite link olish
                elif update.message.forward_from_chat:
                    await update.message.reply_text(
                        "❌ So'rovli kanal uchun forward emas, invite havola yuboring!\n\n"
                        "Havola formati: https://t.me/+XXXXXXXXX"
                    )
                    return
                else:
                    await update.message.reply_text(
                        "❌ So'rovli kanal uchun invite havola yuboring!\n\n"
                        "Havola formati: https://t.me/+XXXXXXXXX"
                    )
                    return
            
            # Forward qilingan xabar
            if update.message.forward_from_chat:
                chat = update.message.forward_from_chat
                channel_id = str(chat.id)
                channel_name = chat.title
                channel_username = chat.username
                
                try:
                    # Botning kanalda admin ekanligini tekshirish
                    bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
                    
                    if not bot_member.status in ['administrator', 'creator']:
                        await update.message.reply_text(
                            "❌ Bot bu kanalda admin emas!\n"
                            "Botni kanalga admin qilib qo'shing va qayta urinib ko'ring."
                        )
                        return
                    
                    # Kanalni bazaga qo'shish
                    if db.add_subscription_channel(channel_id, channel_name, channel_username, is_required, channel_type):
                        if channel_type == 'request':
                            type_text = "🔐 So'rovli kanal"
                        else:
                            type_text = "🔒 Majburiy" if is_required else "🔓 Ixtiyoriy"
                        
                        await update.message.reply_text(
                            f"✅ Kanal muvaffaqiyatli qo'shildi!\n\n"
                            f"📺 Kanal: {channel_name}\n"
                            f"🆔 ID: <code>{channel_id}</code>\n"
                            f"📋 Holati: {type_text}",
                            parse_mode='HTML'
                        )
                        context.user_data['awaiting_channel'] = False
                        context.user_data['channel_is_required'] = True
                        context.user_data['channel_type'] = 'channel'
                    else:
                        await update.message.reply_text("❌ Kanal allaqachon qo'shilgan yoki xatolik yuz berdi!")
                
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Xatolik yuz berdi!\n\n"
                        f"Sabab: {str(e)}\n\n"
                        f"Tekshiring:\n"
                        f"1. Bot kanalda admin ekanligini\n"
                        f"2. Kanal ID to'g'ri ekanligini"
                    )
                return
            
            # Matn sifatida kanal ID yoki username
            elif message_text:
                channel_id = message_text.strip()
                
                try:
                    chat = await context.bot.get_chat(channel_id)
                    
                    # Botning kanalda admin ekanligini tekshirish
                    bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
                    
                    if not bot_member.status in ['administrator', 'creator']:
                        await update.message.reply_text(
                            "❌ Bot bu kanalda admin emas!\n"
                            "Botni kanalga admin qilib qo'shing va qayta urinib ko'ring."
                        )
                        return
                    
                    # Kanalni bazaga qo'shish
                    if db.add_subscription_channel(str(chat.id), chat.title, chat.username, is_required, channel_type):
                        if channel_type == 'request':
                            type_text = "🔐 So'rovli kanal"
                        else:
                            type_text = "🔒 Majburiy" if is_required else "🔓 Ixtiyoriy"
                        
                        await update.message.reply_text(
                            f"✅ Kanal muvaffaqiyatli qo'shildi!\n\n"
                            f"📺 Kanal: {chat.title}\n"
                            f"🆔 ID: <code>{chat.id}</code>\n"
                            f"📋 Holati: {type_text}",
                            parse_mode='HTML'
                        )
                        context.user_data['awaiting_channel'] = False
                        context.user_data['channel_is_required'] = True
                        context.user_data['channel_type'] = 'channel'
                    else:
                        await update.message.reply_text("❌ Kanal allaqachon qo'shilgan yoki xatolik yuz berdi!")
                
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Xatolik yuz berdi!\n\n"
                        f"Sabab: {str(e)}\n\n"
                        f"Tekshiring:\n"
                        f"1. Kanal ID yoki username to'g'ri ekanligini\n"
                        f"2. Bot kanalda admin ekanligini"
                    )
                return
        
        # Instagram profil qo'shish
        if context.user_data.get('awaiting_instagram'):
            if not channel_permission:
                context.user_data['awaiting_instagram'] = False
                await update.message.reply_text("❌ Kanal va profil boshqarish huquqi yo'q!")
                return
            
            if message_text:
                # Instagram linkdan username ajratib olish
                username = message_text.strip()
                
                # Agar link yuborilgan bo'lsa, username ni ajratib olish
                if 'instagram.com/' in username:
                    # https://www.instagram.com/username/ yoki https://instagram.com/username formatidan username olish
                    parts = username.split('instagram.com/')
                    if len(parts) > 1:
                        username = parts[1].split('?')[0].split('/')[0].strip()
                
                # @ belgisini olib tashlash
                username = username.lstrip('@')
                
                if not username or len(username) < 2:
                    await update.message.reply_text("❌ To'g'ri Instagram username yoki link kiriting!")
                    return
                
                # Instagram profilni bazaga qo'shish
                if db.add_instagram_profile(username):
                    await update.message.reply_text(
                        f"✅ Instagram profil muvaffaqiyatli qo'shildi!\n\n"
                        f"📸 Username: @{username}\n"
                        f"🔗 Link: https://instagram.com/{username}",
                        parse_mode='HTML'
                    )
                    context.user_data['awaiting_instagram'] = False
                else:
                    await update.message.reply_text("❌ Bu profil allaqachon qo'shilgan yoki xatolik yuz berdi!")
            return
        
        # Reply keyboard tugmalari
        if message_text == "📊 Statistika":
            await admin_handlers.stats(update, context)
            return
        elif message_text == "📺 Kanal boshqaruvi":
            if not channel_permission:
                await update.message.reply_text("❌ Sizda kanal boshqaruvi huquqi yo'q!")
                return
            await admin_handlers.channel_management(update, context)
            return
        elif message_text == "🎬 Kino boshqaruvi":
            if not movie_permission:
                await update.message.reply_text("❌ Sizda kino boshqaruvi huquqi yo'q!")
                return
            await movie_admin_handlers.movie_management(update, context)
            return
        elif message_text == "📢 Xabar yuborish":
            if not broadcast_permission:
                await update.message.reply_text("❌ Broadcast yuborish huquqi yo'q!")
                return
            clear_broadcast_state(context)
            context.user_data['broadcast_state'] = 'awaiting_content'
            context.user_data['broadcast_data'] = {}
            await update.message.reply_text(
                "📢 <b>Broadcast rejimi</b>\n\n"
                "1️⃣ Matn, rasm yoki video yuboring.\n"
                "2️⃣ Istasangiz tugmalarni qo'shing (Matn - https://link).\n"
                "3️⃣ Tasdiqlang va bot barcha foydalanuvchilarga yuboradi.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="broadcast_cancel")]])
            )
            return
        elif message_text == "💎 Premium obuna":
            if not premium_permission:
                await update.message.reply_text("❌ Premium obunani boshqarish huquqi yo'q!")
                return
            await premium_handlers.send_panel(update, context)
            return
        elif message_text == BOT_SETTINGS_BUTTON_TEXT:
            await admin_handlers.bot_settings(update, context)
            return
        elif message_text == "👑 Admin boshqaruvi":
            if not admin_permission:
                await update.message.reply_text("❌ Adminlarni boshqarish huquqi yo'q!")
                return
            await admin_handlers.admin_management(update, context)
            return
        
        # Video, hujjat yoki audio yuborilsa - kino qo'shish
        if update.message.video or update.message.document or update.message.audio:
            await movie_handlers.add_movie(update, context)
        # Matn yuborilsa - kino qidirish (admin ham kino olishi mumkin)
        elif update.message.text:
            await movie_handlers.get_movie(update, context)
    else:
        premium_flow = context.user_data.get(PREMIUM_FLOW_KEY)
        if premium_flow and premium_flow.get('state') == 'request_pending':
            request_id = premium_flow.get('request_id')
            if request_id:
                request = db.get_premium_request(request_id)
                if request and request.get('status') != 'pending':
                    clear_premium_flow(context)
                    premium_flow = None

        if premium_flow:
            flow_state = premium_flow.get('state')
            if flow_state == 'awaiting_receipt':
                if update.message.photo or update.message.document:
                    await process_premium_receipt_submission(update, context, premium_flow)
                else:
                    await update.message.reply_text(
                        "📎 Iltimos, to'lov chekini PDF yoki skrinshot ko'rinishida yuboring."
                    )
                return
            if flow_state == 'request_pending' and (update.message.photo or update.message.document):
                await update.message.reply_text(
                    "⏳ Chekingiz tekshirilmoqda. Admin tasdiqlashini kuting."
                )
                return

        if message_text == PREMIUM_BUTTON_TEXT:
            settings = db.get_premium_settings()
            if not settings.get('is_active'):
                await update.message.reply_text("Premium obuna hozir faol emas.")
                return

            if premium_flow and premium_flow.get('state') == 'request_pending':
                await update.message.reply_text(
                    "⏳ Chekingiz tekshirilmoqda. Yangi tarif tanlashdan avval admin javobini kuting."
                )
                return

            intro_text = build_premium_intro_text(settings)
            markup = build_premium_plan_keyboard(settings)
            set_premium_flow_state(context, 'awaiting_plan')
            await update.message.reply_text(intro_text, parse_mode='HTML', reply_markup=markup)
            return

        # Oddiy foydalanuvchi - faqat kino qidirish
        if update.message.text:
            await movie_handlers.get_movie(update, context)
        else:
            await update.message.reply_text(
                "❌ Iltimos, kino kodini yuboring!\n"
                "Masalan: <code>ABC12345</code>",
                parse_mode='HTML'
            )


def _extract_receipt_media(message) -> Tuple[Optional[str], Optional[str]]:
    if message.photo:
        return 'photo', message.photo[-1].file_id
    if message.document:
        mime_type = message.document.mime_type or ''
        if mime_type.startswith('image/') or mime_type == 'application/pdf':
            return 'document', message.document.file_id
    return None, None


def _build_admin_request_caption(request: dict, status_text: Optional[str] = None) -> str:
    user_name = request.get('first_name') or "Noma'lum"
    username = request.get('username')
    if username:
        user_name += f" (@{username})"
    status_line = status_text or "⏳ Kutilmoqda"
    plan_label = request.get('plan_label') or '—'
    duration = request.get('duration')
    duration_text = f"{duration} oy" if duration else '—'
    return (
        "🧾 <b>Premium to'lov so'rovi</b>\n\n"
        f"Chek ID: #{request['id']}\n"
        f"👤 Foydalanuvchi: {user_name}\n"
        f"🆔 ID: <code>{request['user_id']}</code>\n"
        f"Tarif: {plan_label}\n"
        f"Muddat: {duration_text}\n"
        f"Summa: {_format_amount(request.get('amount'))}\n"
        f"Holat: {status_line}"
    )


def _build_admin_request_markup(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"premreq:approve:{request_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"premreq:reject:{request_id}")
        ],
        [InlineKeyboardButton("⚠️ To'lov to'liq emas", callback_data=f"premreq:partial:{request_id}")]
    ])


async def notify_premium_admins(bot, request: dict):
    admins = [admin for admin in db.get_admins() if admin.get('can_manage_premium')]
    if not admins:
        admins = db.get_admins()
    if not admins:
        logger.warning("Premium so'rov yuboriladigan admin topilmadi")
        return
    caption = _build_admin_request_caption(request)
    markup = _build_admin_request_markup(request['id'])
    for admin in admins:
        try:
            if request.get('receipt_file_type') == 'photo':
                await bot.send_photo(
                    chat_id=admin['user_id'],
                    photo=request['receipt_file_id'],
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=markup
                )
            else:
                await bot.send_document(
                    chat_id=admin['user_id'],
                    document=request['receipt_file_id'],
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=markup
                )
        except Exception as exc:
            logger.warning(f"Premium so'rovini admin {admin['user_id']} ga yuborib bo'lmadi: {exc}")


async def process_premium_receipt_submission(update: Update, context: ContextTypes.DEFAULT_TYPE, premium_flow: dict):
    message = update.message
    user = update.effective_user
    file_type, file_id = _extract_receipt_media(message)
    if not file_id:
        await message.reply_text("❌ Iltimos, chekni PDF yoki rasm (skrinshot) ko'rinishida yuboring.")
        return

    duration = premium_flow.get('duration')
    amount = premium_flow.get('amount')
    plan_label = premium_flow.get('plan_label') or PREMIUM_PLAN_LABELS.get(duration, f"{duration} oy")
    request_id = db.create_premium_request(
        user_id=user.id,
        first_name=user.first_name,
        username=user.username,
        plan_label=plan_label,
        duration=duration,
        amount=amount,
        receipt_file_id=file_id,
        receipt_file_type=file_type,
        user_chat_id=update.effective_chat.id,
        receipt_message_id=message.message_id
    )
    if not request_id:
        await message.reply_text("❌ Chekni saqlashda xatolik yuz berdi. Iltimos, yana urinib ko'ring.")
        return

    set_premium_flow_state(context, 'request_pending', request_id=request_id)
    await message.reply_text(
        "✅ Chek qabul qilindi!\n\nChek tekshirilmoqda, admin tasdiqlashini kuting."
    )
    request = db.get_premium_request(request_id)
    if request:
        await notify_premium_admins(context.bot, request)


async def handle_user_premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(':', 2)
    if len(parts) < 3:
        await query.answer()
        return
    _, action, value = parts
    settings = db.get_premium_settings()
    if not settings.get('is_active'):
        await query.answer("Premium obuna hozir faol emas", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    if action == 'plan':
        try:
            duration = int(value)
        except ValueError:
            await query.answer()
            return
        amount = _get_plan_price(settings, duration)
        set_premium_flow_state(
            context,
            'plan_selected',
            duration=duration,
            amount=amount,
            plan_label=PREMIUM_PLAN_LABELS.get(duration, f"{duration} oy")
        )
        await query.edit_message_text(
            build_plan_detail_text(duration, amount),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"userprem:confirm:{duration}")],
                [InlineKeyboardButton("◀️ Orqaga", callback_data="userprem:back:0")]
            ])
        )
        await query.answer("Tarif tanlandi", show_alert=False)
        return

    if action == 'back':
        set_premium_flow_state(context, 'awaiting_plan')
        await query.edit_message_text(
            build_premium_intro_text(settings),
            parse_mode='HTML',
            reply_markup=build_premium_plan_keyboard(settings)
        )
        await query.answer("Tariflar ro'yxati", show_alert=False)
        return

    if action == 'cancel':
        clear_premium_flow(context)
        await query.answer("Premium jarayoni bekor qilindi", show_alert=True)
        await query.edit_message_text("❌ Premium obuna jarayoni bekor qilindi.")
        return

    if action == 'confirm':
        try:
            duration = int(value)
        except ValueError:
            await query.answer()
            return
        amount = _get_plan_price(settings, duration)
        plan_label = PREMIUM_PLAN_LABELS.get(duration, f"{duration} oy")
        set_premium_flow_state(
            context,
            'awaiting_receipt',
            duration=duration,
            amount=amount,
            plan_label=plan_label
        )
        await query.edit_message_text(
            build_payment_instruction_text(duration, amount, settings),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Tariflar", callback_data="userprem:back:0")],
                [InlineKeyboardButton("❌ Bekor qilish", callback_data="userprem:cancel:0")]
            ])
        )
        await query.answer("Tasdiqlandi", show_alert=False)
        return

    await query.answer()


async def handle_premium_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if not db.is_admin_user(user_id) or not db.user_has_permission(user_id, 'premium'):
        await query.answer("❌ Bu amal uchun huquq yo'q", show_alert=True)
        return
    parts = query.data.split(':', 2)
    if len(parts) < 3:
        await query.answer()
        return
    _, action, value = parts
    try:
        request_id = int(value)
    except ValueError:
        await query.answer()
        return
    request = db.get_premium_request(request_id)
    if not request:
        await query.answer("So'rov topilmadi", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    if request.get('status') != 'pending':
        await query.answer("Bu chek allaqachon ko'rib chiqilgan", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    status_map = {
        'approve': ('approved', "✅ Chekingiz tasdiqlandi! Premium faollashtirilishi haqida admin bilan bog'lanamiz."),
        'reject': ('rejected', "❌ Chekingiz rad etildi. Iltimos, to'lovni qayta tekshirib, yangidan yuboring."),
        'partial': ('partial', "⚠️ To'lov to'liq emas. Iltimos, qolgan summani to'lab, yangi chek yuboring.")
    }
    if action not in status_map:
        await query.answer()
        return

    new_status, user_message = status_map[action]
    if not db.update_premium_request_status(request_id, new_status, admin_id=user_id):
        await query.answer("Xatolik yuz berdi", show_alert=True)
        return

    status_labels = {
        'approved': '✅ Tasdiqlandi',
        'rejected': '❌ Rad etildi',
        'partial': '⚠️ To\'liq emas'
    }
    try:
        await context.bot.send_message(
            chat_id=request['user_chat_id'],
            text=user_message,
            parse_mode='HTML'
        )
    except Exception as exc:
        logger.warning(f"Premium foydalanuvchiga xabar yuborib bo'lmadi: {exc}")

    caption = _build_admin_request_caption(request, status_labels[new_status])
    try:
        await query.edit_message_caption(caption=caption, parse_mode='HTML', reply_markup=None)
    except Exception:
        try:
            await query.edit_message_text(caption, parse_mode='HTML', reply_markup=None)
        except Exception:
            pass
    await query.answer(status_labels[new_status], show_alert=False)

async def broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast jarayonidagi callback tugmalari"""
    query = update.callback_query
    user_id = query.from_user.id
    if not db.is_admin_user(user_id) or not db.user_has_permission(user_id, 'broadcast'):
        await query.answer("❌ Ushbu amal uchun huquq yo'q!", show_alert=True)
        return
    data = query.data
    if data == 'broadcast_cancel':
        clear_broadcast_state(context)
        await query.answer("Bekor qilindi", show_alert=True)
        try:
            await query.edit_message_text("❌ Xabar yuborish bekor qilindi.")
        except Exception:
            pass
        return
    broadcast_data = context.user_data.get('broadcast_data')
    if data == 'broadcast_reenter_buttons':
        if not broadcast_data:
            await query.answer("Avval xabarni yuboring", show_alert=True)
            return
        context.user_data['broadcast_state'] = 'awaiting_buttons'
        await query.answer("Yangi tugmalarni yuboring", show_alert=False)
        await query.edit_message_text(
            "🔁 Yangi tugmalarni kiriting.\nHar bir qatorda: <code>Matn - https://link</code>.\n\nTugma kerak bo'lmasa, 'skip' deb yozing.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="broadcast_cancel")]])
        )
        return
    if data == 'broadcast_send':
        if not broadcast_data:
            await query.answer("Xabar topilmadi", show_alert=True)
            return
        await query.answer("Yuborilmoqda...", show_alert=False)
        await query.edit_message_text("📤 Xabar yuborilmoqda, biroz kuting...")
        success, failed, total = await broadcast_to_all_users(context.bot, broadcast_data)
        clear_broadcast_state(context)
        if total == 0:
            await query.edit_message_text(
                "❌ Hali bot foydalanuvchilari yo'q. Avval foydalanuvchilar botdan foydalanishi kerak.",
                parse_mode='HTML'
            )
            return
        result_text = (
            "📢 <b>Broadcast yakunlandi</b>\n\n"
            f"👥 Jami foydalanuvchilar: {total}\n"
            f"✅ Yuborildi: {success}\n"
            f"⚠️ Xatolik: {failed}"
        )
        await query.edit_message_text(result_text, parse_mode='HTML')
        return
    await query.answer()

def main():
    """Botni ishga tushirish"""
    # Application yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_handlers.admin_panel))
    application.add_handler(CommandHandler("setchannel", admin_handlers.set_channel))
    application.add_handler(CommandHandler("stats", admin_handlers.stats))
    application.add_handler(CommandHandler("backupdb", admin_handlers.backup_database))
    application.add_handler(CommandHandler("restoredb", admin_handlers.restore_database))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(handle_user_premium_callback, pattern="^userprem:"))
    application.add_handler(CallbackQueryHandler(handle_premium_request_callback, pattern="^premreq:"))
    application.add_handler(CallbackQueryHandler(admin_handlers.channel_callback, pattern="^channel_"))
    application.add_handler(CallbackQueryHandler(admin_handlers.channel_callback, pattern="^instagram_"))
    application.add_handler(CallbackQueryHandler(admin_handlers.admin_callback, pattern="^admin_"))
    application.add_handler(CallbackQueryHandler(admin_handlers.bot_settings_callback, pattern="^botset_"))
    application.add_handler(CallbackQueryHandler(movie_admin_handlers.movie_callback, pattern="^movie_"))
    application.add_handler(CallbackQueryHandler(movie_admin_handlers.movie_callback, pattern="^btn_"))
    application.add_handler(CallbackQueryHandler(premium_handlers.premium_callback, pattern="^premium_"))
    application.add_handler(CallbackQueryHandler(movie_handlers.verify_subscription_callback, pattern="^verify_sub:"))
    application.add_handler(CallbackQueryHandler(broadcast_callback, pattern="^broadcast_"))
    
    # Message handler
    application.add_handler(MessageHandler(
        filters.TEXT | filters.VIDEO | filters.Document.ALL | filters.AUDIO | filters.PHOTO,
        handle_message
    ))
    
    # Botni ishga tushirish
    logger.info("Bot ishga tushdi!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
