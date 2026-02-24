# ocr.py
import logging
from telegram import Update
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore, storage
import io, os
import pytesseract

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# Config va boshqa fayllardan import qilamiz
from config import *
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

STATE_UPLOAD, STATE_VERIFY = range(2)

# --- State 1: Rasm upload ---
async def start_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Iltimos, Rahmat check rasmini yuboring.")
    return STATE_UPLOAD

async def check_upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    img = Image.open(io.BytesIO(photo_bytes))
    text = pytesseract.image_to_string(img, lang='uz+eng')

    if not text.strip():
        await update.message.reply_text("Matn topilmadi. Iltimos qayta yuboring.")
        return STATE_UPLOAD

    payment_info = await extract_payment_info(text)
    check_valid = await Rahmat_check(update.message, payment_info)

    if not check_valid:
        with open("photos/check.jpg", "rb") as photo:
            await update.message.reply_photo(photo)
            await update.message.reply_text(
                "❌ Check noto'g'ri yoki to'liq emas.\nIltimos, to'liq Rahmat check yuboring."
            )
        return STATE_UPLOAD

    # Agar check to'g'ri bo'lsa, keyingi state uchun saqlaymiz
    context.user_data['payment_info'] = payment_info
    context.user_data['photo_bytes'] = photo_bytes

    await update.message.reply_text(
        f"✅ Check ma'lumotlari tekshirilmoqda...\n"
        f"To'lov vaqti: {payment_info['payment_time']}\n"
        f"Summa: {payment_info['amount']} so'm"
    )

    # Keyingi state: telefon raqamini kiritish
    doc_ref = db.collection('payments').document(payment_info['payment_time'])
    doc = doc_ref.get()
    if not doc.exists:
        await update.message.reply_text("❌ Checkingiz bazada topilmadi.")
        return ConversationHandler.END

    fb_phone = doc.to_dict().get('phone')
    context.user_data['fb_phone'] = fb_phone

    await update.message.reply_text(
        f"Telefon raqamingizning so'nggi 4 raqamini kiriting: {fb_phone[:-4]}****"
    )
    return STATE_VERIFY

# --- State 2: Telefon raqamini tekshirish ---
async def check_verify_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    fb_phone = context.user_data.get('fb_phone')
    payment_info = context.user_data.get('payment_info')
    photo_bytes = context.user_data.get('photo_bytes')

    if not user_input or fb_phone[-4:] != user_input[-4:]:
        await update.message.reply_text("❌ Telefon raqam noto'g'ri. Qayta urinib ko'ring.")
        return STATE_VERIFY

    # Paymentni bazadan olib tekshirish
    doc_ref = db.collection('payments').document(payment_info['payment_time'])
    doc = doc_ref.get()
    data = doc.to_dict()
    if data.get('used'):
        await update.message.reply_text("⚠️ Check allaqachon ishlatilgan (used).")
        return ConversationHandler.END

    # Summa tekshiruvi
    amount = float(payment_info['amount'])
    fb_amount = float(data.get('amount', 0))
    if abs(fb_amount - amount)/fb_amount > 0.06:
        await update.message.reply_text("❌ Checkdagi summa FBdagi summa bilan mos emas.")
        return ConversationHandler.END

    # Hammasi to'g'ri bo'lsa: used=True, status=success
    doc_ref.update({"used": True, "status": "success"})

    # Rasmni Storage ga saqlash
    file_name = f"checks/{payment_info['payment_time'].replace(' ', '_')}.jpg"
    blob = bucket.blob(file_name)
    blob.upload_from_string(photo_bytes, content_type='image/jpeg')

    await update.message.reply_text(
        f"✅ To'lov tasdiqlandi. Obunangiz faollashdi!\nTelefon raqamingiz: {fb_phone}"
    )
    return ConversationHandler.END

# --- Start handler ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Jarayon bekor qilindi.")
    return ConversationHandler.END

# --- ConversationHandler setup ---
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start_check', start_check)],
    states={
        STATE_UPLOAD: [MessageHandler(filters.PHOTO, check_upload_handler)],
        STATE_VERIFY: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_verify_handler)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)
conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.PHOTO, check_upload)],
    states={
        CHECK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_phone_handler)]
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
)

# Bot ishga tushurish
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("share", lambda u, c: share(u, c, BOT_USERNAME)))

    # ConversationHandler bilan rasm + telefon tekshiruvi
    app.add_handler(conv_handler)

    print("Bot ishga tushdi...")
    app.run_polling()