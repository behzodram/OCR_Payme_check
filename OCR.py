# ocr.py
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import pytesseract
from config import BOT_TOKEN, BOT_USERNAME
import io, re

# Commands fayldan import qilamiz
from commands import start, stats, help_command, share

# Logger
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# OCR orqali to‘lov ma’lumotlarini ajratib olish
async def extract_payment_info(text):
    # Regex orqali kerakli qismlar
    # Transaction ID
    transaction_match = re.search(r'Tollov identifikatori:\s*(\d+)', text)
    transaction_id = transaction_match.group(1) if transaction_match else "Topilmadi"

    # Amount
    amount_match = re.search(r'To\'?llov summasi:\s*([\d\s,.]+) so\'m', text)
    amount = amount_match.group(1).replace(" ", "") if amount_match else "Topilmadi"

    # Date / Time
    time_match = re.search(r'Tolov vaqti\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', text)
    payment_time = time_match.group(1) if time_match else "Topilmadi"

    return transaction_id, amount, payment_time

# Rasmni qabul qilish va Tesseract OCR
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    img = Image.open(io.BytesIO(photo_bytes))

    # OCR ishlatish (o‘zbek va ingliz tillari)
    text = pytesseract.image_to_string(img, lang='uz+eng')

    if not text.strip():
        text = "Matn topilmadi."

    # To‘lov ma’lumotlarini ajratib olish
    transaction_id, amount, payment_time = await extract_payment_info(text)
    await update.message.reply_text(f"Matn: {text}\n\nTo‘lov ma’lumotlari:\nIdentifikator: {transaction_id}\nSumma: {amount} so'm\nVaqt: {payment_time}")

# Bot ishga tushurish
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Komandalarni qo‘shish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_command))
    # share uchun lambda orqali BOT_USERNAME beriladi
    app.add_handler(CommandHandler("share", lambda u, c: share(u, c, BOT_USERNAME)))

    # Rasm handler
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    print("Bot ishga tushdi...")
    app.run_polling()
