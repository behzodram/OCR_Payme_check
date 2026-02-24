from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram import InputFile

import logging
from PIL import Image
import pytesseract
import firebase_admin
from firebase_admin import credentials, firestore, storage
import io, os, re
import asyncio

from config import *
# Commands fayldan import qilamiz
from commands import start, stats, help_command, share
# OCR definitsiyalarini import qilamiz
from ocr_def import Rahmat_check, extract_payment_info

WAIT_PHONE = 1

# Logger
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

async def firebase_init():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SERVICE_KEY_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

    cred = credentials.Certificate(SERVICE_KEY_PATH)
    firebase_admin.initialize_app(cred, {
        'storageBucket': STORAGE_BUCKET
    })

    db = firestore.client()
    bucket = storage.bucket()
    return db, bucket

# 1️⃣ RASM + CAPTION QABUL QILISH
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Firebase initialization
    db = context.application.bot_data["db"]
    bucket = context.application.bot_data["bucket"]

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    img = Image.open(io.BytesIO(photo_bytes))
    text = pytesseract.image_to_string(img, lang='uz+eng')

    if not text.strip():
        await update.message.reply_text("Matn topilmadi.")
        return ConversationHandler.END

    payment_info = await extract_payment_info(text)
    checkmi = await Rahmat_check(update.message, payment_info)

    if not checkmi:
        with open("photos/check.jpg", "rb") as photo:
            await update.message.reply_text(
                "❌ Check noto'g'ri yoki to'liq emas.\n\n"
                "Iltimos, quyidagi namunaga o'xshash to'liq Rahmat check yuboring 👇"
            )
            await update.message.reply_photo(photo)
        return ConversationHandler.END

    await update.message.reply_text(
        "📸 Rasm qabul qilindi.\n"
        "    To'lov ma'lumotlari:\n"
        "    Identifikator: {payment_info['transaction_id']}\n"
        "    Xizmat: {payment_info['payment_service']}\n"
        "    Summa: {payment_info['amount']} so'm\n"
        "    Vaqt: {payment_info['payment_time']}\n\n"
        "📱 Endi telefon raqamingizni kiriting:"
    )

    context.user_data["payment_info"] = payment_info
    context.user_data["checkmi"] = checkmi 
    
    context.user_data["photo_file_id"] = await update.message.photo[-1].file_id
    
    return WAIT_PHONE


# 2️⃣ TELEFONNI TEKSHIRISH
async def phone_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Firebase initialization
    db = context.application.bot_data["db"]
    bucket = context.application.bot_data["bucket"]

    user_phone = await update.message.text.strip()
    caption_text = context.user_data.get("caption_text")

    if not caption_text:
        await update.message.reply_text("❌ Caption topilmadi.")
        return ConversationHandler.END

    # Oddiy taqqoslash (caption ichida telefon mavjudligini tekshiramiz)
    if user_phone in caption_text:
        await update.message.reply_text("✅ Mos keldi.")
    else:
        await update.message.reply_text("❌ Mos kelmadi.")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END


async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Firebase init
    db, bucket = await firebase_init()

    # Global saqlaymiz
    app.bot_data["db"] = db
    app.bot_data["bucket"] = bucket

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, photo_handler)],
        states={
            WAIT_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_check_handler)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))

    app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())