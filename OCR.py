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
from telegram import InputFile

async def Rahmat_check(update, payment_info):

    if not (
        payment_info.get("transaction_id") and
        payment_info.get("amount") and
        payment_info.get("payment_time") and
        payment_info.get("payment_service")
    ):
        return False  # Check noto‘g‘ri yoki to‘liq emas
    return True  # Check to‘g‘ri va to‘liq
    
# OCR orqali to‘lov ma’lumotlarini ajratib olish
async def extract_payment_info(text: str):
    # Textni normalize qilamiz
    clean_text = text.replace("’", "'").replace("`", "'")

    # Transaction ID (identifikatori yoki id= holatlari uchun)
    transaction_match = re.search(
        r'(?:identifikatori)[^\d]*(\d{5,})',
        clean_text,
        re.IGNORECASE
    )
    transaction_id = transaction_match.group(1) if transaction_match else None

    # Amount (so'm, som, so m variantlari uchun)
    amount_match = re.search(
        r'summasi[^\d]*([\d\s,.]+)',
        clean_text,
        re.IGNORECASE
    )

    amount = None
    if amount_match:
        amount = re.sub(r'[^\d.]', '', amount_match.group(1))

    # Date / Time
    time_match = re.search(
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
        clean_text
    )
    payment_time = time_match.group(1) if time_match else None

    # Payment Service
    service_match = re.search(
        r'xizmati[:\s]+([a-z]+)',
        clean_text,
        re.IGNORECASE
    )
    payment_service = service_match.group(1) if service_match else None

    return {
        "transaction_id": transaction_id,
        "payment_service": payment_service,
        "amount": amount,
        "payment_time": payment_time,
    }

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
    payment_info = await extract_payment_info(text)
    checkmi = await Rahmat_check(update.message, payment_info)
    if not checkmi:
        with open("photos/check.jpg", "rb") as photo:
            await update.message.reply_text(
                "❌ Check noto‘g‘ri yoki to‘liq emas.\n\n"
                "Iltimos, quyidagi namunaga o‘xshash to‘liq Rahmat check yuboring 👇"
            )

            await update.message.reply_photo(photo)
    else:
        await update.message.reply_text("✅ Check qabul qilindi.")
        await update.message.reply_text(f"To‘lov ma’lumotlari:\nIdentifikator: {payment_info['transaction_id']}\nXizmat: {payment_info['payment_service']}\nSumma: {payment_info['amount']} so'm\nVaqt: {payment_info['payment_time']}")

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
