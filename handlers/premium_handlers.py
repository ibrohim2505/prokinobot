from typing import Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import DatabaseManager


class PremiumHandlers:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def _has_access(self, user_id: int) -> bool:
        return self.db.is_admin_user(user_id) and self.db.user_has_permission(user_id, 'premium')

    def _format_amount(self, amount: Optional[int]) -> str:
        if amount is None:
            return "—"
        formatted = f"{amount:,}".replace(',', ' ')
        return f"{formatted} so'm"

    def _build_panel(self) -> Tuple[str, InlineKeyboardMarkup]:
        settings = self.db.get_premium_settings()
        stats = self.db.get_premium_stats()
        status_text = "🟢 Faol" if settings['is_active'] else "❌ O'chirilgan"
        text = (
            "💎 <b>Premium Obuna Boshqaruvi</b>\n\n"
            f"📊 <b>Holat:</b> {status_text}\n"
            f"👥 <b>Premium foydalanuvchilar:</b> {stats['active_users']} ta\n\n"
            "💰 <b>Narxlar:</b>\n"
            f"• 1 oy: {self._format_amount(settings['price_1m'])}\n"
            f"• 3 oy: {self._format_amount(settings['price_3m'])}\n"
            f"• 6 oy: {self._format_amount(settings['price_6m'])}\n"
            f"• 12 oy: {self._format_amount(settings['price_12m'])}\n\n"
            f"📝 <b>Tavsif:</b> {settings['description']}"
        )
        keyboard = [
            [
                InlineKeyboardButton("💰 Narxlar sozlash", callback_data="premium_prices"),
                InlineKeyboardButton("✏️ Tavsif o'zgartirish", callback_data="premium_description")
            ],
            [
                InlineKeyboardButton(status_text, callback_data="premium_toggle"),
                InlineKeyboardButton("📊 Premium statistika", callback_data="premium_stats")
            ],
            [
                InlineKeyboardButton("🧾 To'lovlar", callback_data="premium_payments"),
                InlineKeyboardButton("💳 Karta qo'shish", callback_data="premium_card")
            ],
            [
                InlineKeyboardButton("👥 Premium foydalanuvchilar", callback_data="premium_users")
            ]
        ]
        return text, InlineKeyboardMarkup(keyboard)

    def _remember_panel_message(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
        context.user_data['premium_message'] = {'chat_id': chat_id, 'message_id': message_id}

    async def _restore_panel_from_storage(self, context: ContextTypes.DEFAULT_TYPE, bot) -> bool:
        stored = context.user_data.get('premium_message')
        if not stored:
            return False
        text, markup = self._build_panel()
        try:
            await bot.edit_message_text(
                chat_id=stored['chat_id'],
                message_id=stored['message_id'],
                text=text,
                parse_mode='HTML',
                reply_markup=markup
            )
            return True
        except Exception:
            return False

    def _cancel_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Bekor qilish", callback_data="premium_cancel")]])

    async def send_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._has_access(update.effective_user.id):
            await update.message.reply_text("❌ Premium obunani boshqarish huquqi yo'q!")
            return
        text, markup = self._build_panel()
        message = await update.message.reply_text(text, parse_mode='HTML', reply_markup=markup)
        self._remember_panel_message(context, message.chat_id, message.message_id)
        context.user_data.pop('premium_state', None)

    async def _render_panel(self, query, context: ContextTypes.DEFAULT_TYPE):
        text, markup = self._build_panel()
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=markup)
        self._remember_panel_message(context, query.message.chat_id, query.message.message_id)

    async def premium_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        if not self._has_access(user_id):
            await query.answer("❌ Premium bo'limi uchun huquq yo'q!", show_alert=True)
            return
        data = query.data
        self._remember_panel_message(context, query.message.chat_id, query.message.message_id)
        if data == "premium_refresh":
            await query.answer("Yangilandi", show_alert=False)
            await self._render_panel(query, context)
            context.user_data.pop('premium_state', None)
            return
        if data == "premium_prices":
            context.user_data['premium_state'] = 'prices'
            await query.answer("Narxlarni yuboring", show_alert=False)
            await query.edit_message_text(
                "💰 <b>Narxlarni yangilash</b>\n\n"
                "Har bir qatorda muddat va summani kiriting.\n"
                "Masalan:\n"
                "1 oy - 12000\n3 oy - 36000\n6 oy - 60000\n12 oy - 110000",
                parse_mode='HTML',
                reply_markup=self._cancel_keyboard()
            )
            return
        if data == "premium_description":
            context.user_data['premium_state'] = 'description'
            await query.answer("Tavsifni yuboring", show_alert=False)
            await query.edit_message_text(
                "✏️ <b>Tavsifni yangilash</b>\n\nYangi tavsif matnini yuboring.",
                parse_mode='HTML',
                reply_markup=self._cancel_keyboard()
            )
            return
        if data == "premium_card":
            context.user_data['premium_state'] = 'card'
            await query.answer("Karta ma'lumotini yuboring", show_alert=False)
            await query.edit_message_text(
                "💳 <b>Karta qo'shish</b>\n\nKarta raqami va nomini yuboring.",
                parse_mode='HTML',
                reply_markup=self._cancel_keyboard()
            )
            return
        if data == "premium_cancel":
            context.user_data.pop('premium_state', None)
            await query.answer("Bekor qilindi", show_alert=True)
            await self._render_panel(query, context)
            return
        if data == "premium_toggle":
            new_state = self.db.toggle_premium_status()
            if new_state is None:
                await query.answer("Xatolik yuz berdi", show_alert=True)
                return
            message = "Premium obuna faollashtirildi" if new_state else "Premium obuna o'chirildi"
            await query.answer(message, show_alert=True)
            await self._render_panel(query, context)
            return
        if data == "premium_stats":
            stats = self.db.get_premium_stats()
            text = (
                "📊 <b>Premium statistika</b>\n\n"
                f"Jami premium foydalanuvchilar: {stats['total_users']} ta\n"
                f"Faol obunalar: {stats['active_users']} ta\n"
                f"Qayd etilgan to'lovlar: {stats['total_payments']} ta"
            )
            await query.answer("Statistika", show_alert=False)
            await query.message.reply_text(text, parse_mode='HTML')
            return
        if data == "premium_users":
            users = self.db.get_premium_users()
            if not users:
                body = "Hozircha premium foydalanuvchilar yo'q."
            else:
                lines = []
                for idx, user in enumerate(users, start=1):
                    name = user['first_name'] or "Noma'lum"
                    if user['username']:
                        name += f" (@{user['username']})"
                    plan = user['plan'] or '—'
                    expires = user['expires_at'] or '—'
                    lines.append(f"{idx}. {name} - {plan} (tugash: {expires})")
                body = '\n'.join(lines)
            await query.answer("Foydalanuvchilar", show_alert=False)
            await query.message.reply_text(
                "👥 <b>Premium foydalanuvchilar</b>\n\n" + body,
                parse_mode='HTML'
            )
            return
        if data == "premium_payments":
            payments = self.db.get_premium_payments()
            if not payments:
                body = "Hali to'lovlar qayd etilmagan."
            else:
                lines = []
                for payment in payments:
                    amount = self._format_amount(payment['amount'])
                    duration = payment['duration'] or 0
                    method = payment['payment_method'] or '—'
                    reference = payment['reference'] or '—'
                    lines.append(
                        f"• {amount} / {duration} oy\n  Usul: {method}\n  Chek: {reference}\n"
                    )
                body = '\n'.join(lines)
            await query.answer("To'lovlar", show_alert=False)
            await query.message.reply_text(
                "🧾 <b>So'nggi to'lovlar</b>\n\n" + body,
                parse_mode='HTML'
            )
            return
        await query.answer()

    def _parse_prices(self, text: str) -> dict:
        values = {}
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for line in lines:
            cleaned = line.replace('oy', '').replace("so'm", '').replace('som', '')
            for sep in [':', '-', '=', ',']:
                cleaned = cleaned.replace(sep, ' ')
            parts = [p for p in cleaned.split() if p]
            if len(parts) < 2:
                raise ValueError("Format noto'g'ri")
            duration = ''.join(ch for ch in parts[0] if ch.isdigit())
            amount = ''.join(ch for ch in parts[1] if ch.isdigit())
            if not duration or not amount:
                raise ValueError("Raqam kiriting")
            duration = int(duration)
            amount = int(amount)
            if duration not in (1, 3, 6, 12):
                raise ValueError("Muddat 1/3/6/12 oy bo'lishi kerak")
            values[duration] = amount
        if set(values.keys()) != {1, 3, 6, 12}:
            raise ValueError("Barcha muddatlarni kiriting")
        return values

    async def handle_state_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        state = context.user_data.get('premium_state')
        if not state:
            return False
        if not self._has_access(update.effective_user.id):
            context.user_data.pop('premium_state', None)
            await update.message.reply_text("❌ Premium bo'limi uchun huquq yo'q!")
            return True
        text = update.message.text or ''
        if state == 'prices':
            try:
                prices = self._parse_prices(text)
            except ValueError as exc:
                await update.message.reply_text(f"❌ {exc}")
                return True
            success = self.db.update_premium_prices(
                prices[1], prices[3], prices[6], prices[12]
            )
            if success:
                await update.message.reply_text("✅ Narxlar yangilandi")
            else:
                await update.message.reply_text("❌ Narxlarni saqlab bo'lmadi")
            context.user_data.pop('premium_state', None)
            await self._restore_panel_from_storage(context, context.bot)
            return True
        if state == 'description':
            if len(text.strip()) < 10:
                await update.message.reply_text("❌ Tavsif kamida 10 ta belgidan iborat bo'lishi kerak")
                return True
            success = self.db.update_premium_description(text.strip())
            if success:
                await update.message.reply_text("✅ Tavsif yangilandi")
            else:
                await update.message.reply_text("❌ Tavsifni saqlab bo'lmadi")
            context.user_data.pop('premium_state', None)
            await self._restore_panel_from_storage(context, context.bot)
            return True
        if state == 'card':
            if len(text.strip()) < 10:
                await update.message.reply_text("❌ Karta ma'lumotlari to'liq emas")
                return True
            success = self.db.update_premium_card(text.strip())
            if success:
                await update.message.reply_text("✅ Karta ma'lumotlari yangilandi")
            else:
                await update.message.reply_text("❌ Ma'lumotni saqlab bo'lmadi")
            context.user_data.pop('premium_state', None)
            await self._restore_panel_from_storage(context, context.bot)
            return True
        return False
