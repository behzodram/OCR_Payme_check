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

def firebase_init():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SERVICE_KEY_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

    cred = credentials.Certificate(SERVICE_KEY_PATH)
    firebase_admin.initialize_app(cred, {
        'storageBucket': STORAGE_BUCKET
    })

    db = firestore.client()
    bucket = storage.bucket()
    return db, bucket

async def firebase_phone(db, payment_time, update:Update):
    # Firestore collection: payments
    doc_ref = db.collection('payments').document(payment_time)
    doc = doc_ref.get()

    if not doc.exists:
        await update.message.reply_text("❌ Checkingiz Bazada topilmadi.")
        return ConversationHandler.END
        
    data = doc.to_dict()
    fb_phone = data.get("phone")
    if not fb_phone:
        await update.message.reply_text("❌ Telefon raqam topilmadi.")
        return ConversationHandler.END
    return fb_phone
    


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

    fb_phone = await firebase_phone(db, payment_info['payment_time'], update)

    await update.message.reply_text(
        "📸 Rasm qabul qilindi.\n"
        "To'lov ma'lumotlari:\n\n"
        f"Identifikator: {payment_info['transaction_id']}\n"
        f"Xizmat: {payment_info['payment_service']}\n"
        f"Summa: {payment_info['amount']} so'm\n"
        f"Vaqt: {payment_info['payment_time']}\n\n"
        f"📱 Endi {fb_phone[:-4]}-xx-xx ni songgi 4 raqamini kiriting:"
    )

    context.user_data["payment_info"] = payment_info
    context.user_data["checkmi"] = checkmi 
    
    # context.user_data["photo_file_id"] = await update.message.photo[-1].file_id
    
    return WAIT_PHONE


# 2️⃣ TELEFONNI TEKSHIRISH
async def phone_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Firebase initialization
    db = context.application.bot_data["db"]
    bucket = context.application.bot_data["bucket"]

    user_phone = update.message.text.strip()
    payment_info = context.user_data.get("payment_info")
    checkmi = context.user_data.get("checkmi")
    
    if not payment_info or not checkmi:
        await update.message.reply_text("❌ Ichki xatolik yuz berdi. Iltimos, rasmni qayta yuboring.")
        return ConversationHandler.END
    
    fb_phone = await firebase_phone(db, payment_info['payment_time'], update)
    if not fb_phone:
        await update.message.reply_text("❌ Telefon raqam topilmadi.")
        return ConversationHandler.END
    
    if user_phone != fb_phone[-4:]:
        await update.message.reply_text("❌ Telefon raqam mos kelmadi. Iltimos, qayta urinib ko'ring.")
        return ConversationHandler.END
    await update.message.reply_text("📱 Telefon raqami mos chiqdi.")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Firebase init
    db, bucket = firebase_init()

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
    main()