# ocr.py
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from PIL import Image
import pytesseract
from config import *
import firebase_admin
from firebase_admin import credentials, firestore, storage
import io, os

# from datetime import datetime

# Commands fayldan import qilamiz
from commands import start, stats, help_command, share
# OCR definitsiyalarini import qilamiz
from ocr_def import Rahmat_check, extract_payment_info

# Logger
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
from telegram import InputFile


# ===============================
# 🔥 FIREBASE INIT
# ===============================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_KEY_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

cred = credentials.Certificate(SERVICE_KEY_PATH)
firebase_admin.initialize_app(cred, {
    'storageBucket': STORAGE_BUCKET
})

db = firestore.client()
bucket = storage.bucket()

CHECK_PHOTO, WAIT_PHONE = range(2)

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    img = Image.open(io.BytesIO(photo_bytes))
    text = pytesseract.image_to_string(img, lang='uz+eng')

    if not text.strip():
        await update.message.reply_text("❌ Matn topilmadi.")
        return ConversationHandler.END

    payment_info = await extract_payment_info(text)

    if not payment_info:
        await update.message.reply_text("❌ Check noto‘g‘ri.")
        return ConversationHandler.END

    payment_time = payment_info.get("payment_time")

    doc_ref = db.collection("payments").document(payment_time)
    doc = doc_ref.get()

    if not doc.exists:
        await update.message.reply_text("❌ Checkingiz bazada topilmadi.")
        return ConversationHandler.END

    data = doc.to_dict()

    if data.get("used"):
        await update.message.reply_text("⚠️ Check allaqachon ishlatilgan.")
        return ConversationHandler.END

    fb_phone = data.get("phone")
    if not fb_phone:
        await update.message.reply_text("❌ Telefon raqam topilmadi.")
        return ConversationHandler.END

    # 🔥 USER_DATA ga saqlaymiz
    context.user_data["payment_time"] = payment_time
    context.user_data["photo_bytes"] = photo_bytes
    context.user_data["fb_phone"] = fb_phone
    context.user_data["fb_amount"] = float(data.get("amount", 0))

    # Maskalangan ko‘rinish
    masked = fb_phone[:-4] + "xxxx"

    await update.message.reply_text(
        f"Telefon raqamingiz: {masked}\n\n"
        "Iltimos, telefon raqamingizning so‘nggi 4 raqamini kiriting:"
    )

    return WAIT_PHONE


async def phone_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_last4 = update.message.text.strip()

    fb_phone = context.user_data.get("fb_phone")
    payment_time = context.user_data.get("payment_time")
    photo_bytes = context.user_data.get("photo_bytes")
    fb_amount = context.user_data.get("fb_amount")

    if not fb_phone:
        await update.message.reply_text("❌ Sessiya muddati tugagan. Qayta urinib ko‘ring.")
        return ConversationHandler.END

    if user_last4 != fb_phone[-4:]:
        await update.message.reply_text("❌ So‘nggi 4 raqam noto‘g‘ri. Qayta kiriting:")
        return WAIT_PHONE

    # 🔥 Hamma narsa to‘g‘ri — status update
    doc_ref = db.collection("payments").document(payment_time)

    doc_ref.update({
        "used": True,
        "status": "success"
    })

    # Storage ga yuklash
    file_name = f"checks/{payment_time.replace(' ', '_')}.jpg"
    blob = bucket.blob(file_name)
    blob.upload_from_string(photo_bytes, content_type="image/jpeg")

    await update.message.reply_text(
        f"✅ To‘lov tasdiqlandi!\nTelefon: {fb_phone}"
    )

    # Sessiyani tozalaymiz
    context.user_data.clear()

    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.PHOTO, photo_handler)],
    states={
        WAIT_PHONE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, phone_check_handler)
        ]
    },
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
)

# Bot ishga tushurish
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Komandalarni qo'shish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_command))
    # share uchun lambda orqali BOT_USERNAME beriladi
    app.add_handler(CommandHandler("share", lambda u, c: share(u, c, BOT_USERNAME)))

    # Rasm handler
    app.add_handler(conv_handler)
    
    print("Bot ishga tushdi...")
    app.run_polling()
