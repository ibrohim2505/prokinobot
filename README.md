# 🎬 Kino Bot

Telegram bot - kinolarni boshqarish va ulashish uchun.

## 📋 Funksiyalar

- ✅ Admin panel
- ✅ Baza kanal sozlamalari
- ✅ Kinolarni baza kanalga yuklash
- ✅ Noyob kod generatsiya qilish
- ✅ Kino kodiga qarab kinoni topish va yuborish
- ✅ Statistika

## 🚀 O'rnatish

1. Kutubxonalarni o'rnatish:

```bash
pip install -r requirements.txt
```

2. Botni ishga tushirish:

```bash
python bot.py
```

## ⚙️ Sozlash

### Muhit o'zgaruvchilari

| O'zgaruvchi     | Tavsif                    | Standart qiymat            |
|-----------------|---------------------------|----------------------------|
| `BOT_TOKEN`     | Telegram bot tokeni       | `config.py` dagi default   |
| `ADMIN_ID`      | Super admin ID            | `config.py` dagi default   |
| `DATABASE_PATH` | SQLite faylining manzili  | `database/movies.db`       |

`.env` faylida yoki Railway/Render kabi hosting platformalarida ushbu qiymatlarni berib, kodni o'zgartirmasdan sozlamalarni boshqarishingiz mumkin.

### 1. Baza kanalini yaratish

- Telegram'da yangi kanal yarating (masalan: Movie Storage)
- Botni kanalga admin qilib qo'shing
- Botga "Xabar yuborish" huquqini bering

### 2. Baza kanalini sozlash

Botda `/setchannel` buyrug'ini yuboring:

```text
/setchannel -1001234567890
```

yoki

```text
/setchannel @channelname
```

Kanal ID ni topish uchun:

- Botni kanalga admin qiling
- Kanaldan biror xabarni @userinfobot ga forward qiling
- Bot sizga kanal ID ni beradi

## 📱 Foydalanish

### Admin uchun

**Buyruqlar:**

- `/start` - Botni ishga tushirish
- `/admin` - Admin panel
- `/setchannel` - Baza kanalini sozlash
- `/stats` - Statistika
- `/backupdb` - Database nusxasini yuklab olish (faqat super admin)
- `/help` - Yordam

**Kino qo'shish:**

1. Kinoni botga yuboring (video, hujjat yoki audio)
2. Bot kinoni baza kanalga yuklaydi
3. Bot sizga noyob kodni beradi (masalan: ABC12345)

### Foydalanuvchi uchun

**Kinoni olish:**

1. Botga kino kodini yuboring
2. Bot kinoni topib yuboradi

## 📂 Loyiha strukturasi

```text
prokinobot/
├── bot.py                 # Asosiy bot fayli
├── config.py              # Konfiguratsiya
├── requirements.txt       # Kutubxonalar
├── database/
│   ├── __init__.py
│   ├── db_manager.py      # Database boshqaruvi
│   └── movies.db          # SQLite database (avtomatik yaratiladi)
├── handlers/
│   ├── __init__.py
│   ├── admin_handlers.py  # Admin buyruqlari
│   └── movie_handlers.py  # Kino bilan ishlash
└── utils/                 # Yordamchi funksiyalar (kelajakda)
```

## 🔧 Texnologiyalar

- Python 3.8+
- python-telegram-bot 20.7
- SQLite3

## 📝 Izoh

Bot to'liq ishga tayyor. Faqat:

1. Kutubxonalarni o'rnating
2. Baza kanalini sozlang
3. Kinolarni qo'shing va foydalaning!

## 💾 Ma'lumotlarni saqlash va serverni almashtirish

- Bot barcha ma'lumotlarni `database/movies.db` fayliga yozadi (kinolar, foydalanuvchilar, adminlar, sozlamalar va h.k.).
- Serverni almashtirishdan oldin ushbu faylni saqlab qo'ying va yangi serverdagi `database/` papkasiga nusxa ko'chiring.
- Super admin `/backupdb` buyrug'i orqali joriy database faylini botning o'zidan yuklab olishi mumkin.
- Yangi serverga o'tganda `database/movies.db` faylini joylashtirgandan so'ng botni ishga tushiring — barcha ma'lumotlar tiklanadi.

### 🚀 Railway ga deploy qilish (TO'G'RI USUL)

⚠️ **MUHIM**: Railway da oddiy deploy qilsangiz, har safar redeploy qilganda ma'lumotlar yo'qoladi! Buning oldini olish uchun quyidagi qadamlarni bajaring:

#### 1-usul: Railway Volume (Tavsiya etiladi)

1. Railway projectingizga kiring
2. Bot servisingizni bosing
3. **Settings** → **Volumes** bo'limiga o'ting
4. **+ New Volume** bosing:
   - Mount Path: `/app/data`
   - Volume nomi: `movies-data`
5. **Variables** bo'limiga quyidagilarni qo'shing:

   ```bash
   BOT_TOKEN=sizning_token
   ADMIN_ID=sizning_admin_id
   DATABASE_PATH=/app/data/movies.db
   ```

6. Deploy qiling

Volume ulangandan keyin barcha ma'lumotlar saqlanib qoladi!

#### 2-usul: PostgreSQL (Eng ishonchli)

1. Railway projectingizda **+ New** → **Database** → **PostgreSQL** qo'shing
2. PostgreSQL yaratilgandan keyin **Connect** tugmasini bosing
3. `DATABASE_URL` avtomatik environment variablega qo'shiladi
4. Bot avtomatik PostgreSQL ga ulanadi (kod tayyor)

#### 3-usul: Muntazam backup

Agar yuqoridagi usullar ishlamasa:

1. Bot sozlamalarida **💾 Database backup** bosing
2. Database faylini kompyuteringizga saqlang
3. Har safar redeploy qilishdan oldin backup oling
4. Kerak bo'lganda `/restoredb` orqali tiklang

### 📋 Railway Environment Variables

| O'zgaruvchi | Tavsif | Misol |
| --- | --- | --- |
| `BOT_TOKEN` | Telegram bot tokeni | `123456:ABC-DEF...` |
| `ADMIN_ID` | Super admin Telegram ID | `5425876649` |
| `DATABASE_PATH` | SQLite fayl joylashuvi | `/app/data/movies.db` |
| `DATABASE_URL` | PostgreSQL URL (Railway beradi) | `postgresql://...` |

### ⚠️ Ma'lumot yo'qolishining oldini olish

1. **Har doim backup oling** - Bot sozlamalarida "Database backup" tugmasi bor
2. **Volume ishlating** - Railway Volume ishlatish eng oson usul
3. **PostgreSQL ishlating** - Katta loyihalar uchun eng yaxshi tanlov
4. **Git ga database yuklamang** - `.gitignore` da `*.db` qo'shilgan

## 🆘 Muammolar

Agar bot baza kanalga xabar yubora olmasa:

1. Botni kanalga admin qilib qo'shganingizni tekshiring
2. Botga "Xabar yuborish" huquqini berganingizni tekshiring
3. Kanal ID to'g'ri kiritilganini tekshiring

## 📞 Aloqa

Savol va takliflar uchun: @manager_komilov

---

Made with ❤️ by GitHub Copilot
