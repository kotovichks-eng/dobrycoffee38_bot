import os
import io
import qrcode
import psycopg2
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

BONUS_LIMIT = 6
ADMIN_IDS = [704720490]

# --- Подключение к базе ---
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    bonus INTEGER DEFAULT 0
);
""")
conn.commit()

# --- Старт ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    cursor.execute(
        "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING;",
        (user_id,)
    )
    conn.commit()

    keyboard = [["☕ Мои бонусы"], ["🔳 Мой QR"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "☕ Добрый кофе\n\nСоберите 6 чашек — 7-я бесплатно 🎁",
        reply_markup=markup
    )

# --- Показ бонусов ---
async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT bonus FROM users WHERE user_id=%s;", (user_id,))
    result = cursor.fetchone()
    bonus = result[0] if result else 0

    await update.message.reply_text(
        f"У вас {bonus} бонусных чашек ☕\n"
        f"До бесплатной осталось: {BONUS_LIMIT - bonus}"
    )

# --- Генерация QR ---
async def qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    qr_img = qrcode.make(str(user_id))

    bio = io.BytesIO()
    bio.name = "qr.png"
    qr_img.save(bio, "PNG")
    bio.seek(0)

    await update.message.reply_photo(
        photo=bio,
        caption="Покажите этот QR бариста для начисления бонуса ☕"
    )

# --- Начисление чашек (только админ) ---
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Нет доступа")
        return

    if len(context.args) == 0:
        await update.message.reply_text("Использование: /add ID_клиента")
        return

    user_id = int(context.args[0])

    cursor.execute("SELECT bonus FROM users WHERE user_id=%s;", (user_id,))
    result = cursor.fetchone()

    if result:
        bonus = result[0] + 1

        if bonus >= BONUS_LIMIT:
            cursor.execute(
                "UPDATE users SET bonus=0 WHERE user_id=%s;",
                (user_id,)
            )
            conn.commit()
            await update.message.reply_text("🎉 Клиент получил бесплатную чашку!")
        else:
            cursor.execute(
                "UPDATE users SET bonus=%s WHERE user_id=%s;",
                (bonus, user_id)
            )
            conn.commit()
            await update.message.reply_text(
                f"Добавлена чашка ☕ Теперь у клиента {bonus}"
            )
    else:
        await update.message.reply_text("Клиент не найден")

# --- Запуск ---
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bonus", bonus))
app.add_handler(CommandHandler("qr", qr))
app.add_handler(CommandHandler("add", add))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

app.run_polling()
