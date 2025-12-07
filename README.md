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

| O'zgaruvchi | Tavsif | Standart qiymat |
|-------------|--------|-----------------|
| `BOT_TOKEN` | Telegram bot tokeni | `config.py` dagi default |
| `ADMIN_ID`  | Super admin ID | `config.py` dagi default |
| `DATABASE_PATH` | SQLite faylining manzili | `database/movies.db` |

`.env` faylida yoki Railway/Render kabi hosting platformalarida ushbu qiymatlarni berib, kodni o'zgartirmasdan sozlamalarni boshqarishingiz mumkin.

### 1. Baza kanalini yaratish
- Telegram'da yangi kanal yarating (masalan: Movie Storage)
- Botni kanalga admin qilib qo'shing
- Botga "Xabar yuborish" huquqini bering

### 2. Baza kanalini sozlash
Botda `/setchannel` buyrug'ini yuboring:
```
/setchannel -1001234567890
```
yoki
```
/setchannel @channelname
```

Kanal ID ni topish uchun:
- Botni kanalga admin qiling
- Kanaldan biror xabarni @userinfobot ga forward qiling
- Bot sizga kanal ID ni beradi

## 📱 Foydalanish

### Admin uchun:

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

### Foydalanuvchi uchun:

**Kinoni olish:**
1. Botga kino kodini yuboring
2. Bot kinoni topib yuboradi

## 📂 Loyiha strukturasi

```
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

### ♻️ Railway (yoki boshqa PaaS) da ma'lumotni yo'qotmaslik

Railway konteyneri qayta ishga tushganida lokal fayllar yo'qoladi. SQLite bazasini saqlab qolish uchun quyidagi bosqichlarni bajaring:

1. Railway project ➝ **Volumes** bo'limidan `+ New Volume` bosing (masalan, `movies-data`).
2. Ushbu volume'ni bot servisiga ulab, masalan `/app/data` papkasiga mount qiling.
3. Railway dagi **Variables** bo'limiga `DATABASE_PATH=/app/data/movies.db` ni qo'shing.
4. Deploy qayta ishga tushgach, barcha ma'lumotlar volume ichida saqlanadi va redeploy/paydo bo'ladigan restartlardan keyin ham saqlanib qoladi.

Volume ulash imkoni bo'lmasa, tashqi Postgres/MySQL xizmatidan foydalaning yoki `/backupdb` orqali muntazam backup olib boring.

## 🆘 Muammolar

Agar bot baza kanalga xabar yubora olmasa:
1. Botni kanalga admin qilib qo'shganingizni tekshiring
2. Botga "Xabar yuborish" huquqini berganingizni tekshiring
3. Kanal ID to'g'ri kiritilganini tekshiring

## 📞 Aloqa

Savol va takliflar uchun: @YourUsername

---

Made with ❤️ by GitHub Copilot
