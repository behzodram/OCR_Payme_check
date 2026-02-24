# ocr.py
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import pytesseract
from config import BOT_TOKEN, BOT_USERNAME
import firebase_admin
from firebase_admin import credentials, firestore, storage
import io

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

# Rasmni qabul qilish va Tesseract OCR
# async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     photo_file = await update.message.photo[-1].get_file()
#     photo_bytes = await photo_file.download_as_bytearray()

#     img = Image.open(io.BytesIO(photo_bytes))

#     # OCR ishlatish (o'zbek va ingliz tillari)
#     text = pytesseract.image_to_string(img, lang='uz+eng')

#     if not text.strip():
#         text = "Matn topilmadi."

#     # To'lov ma'lumotlarini ajratib olish
#     payment_info = await extract_payment_info(text)
#     checkmi = await Rahmat_check(update.message, payment_info)
#     if not checkmi:
#         with open("photos/check.jpg", "rb") as photo:
#             await update.message.reply_text(
#                 "❌ Check noto'g'ri yoki to'liq emas.\n\n"
#                 "Iltimos, quyidagi namunaga o'xshash to'liq Rahmat check yuboring 👇"
#             )

#             await update.message.reply_photo(photo)
#     else:
#         await update.message.reply_text("✅ Check qabul qilindi.")
#         await update.message.reply_text(f"To'lov ma'lumotlari:\nIdentifikator: {payment_info['transaction_id']}\nXizmat: {payment_info['payment_service']}\nSumma: {payment_info['amount']} so'm\nVaqt: {payment_info['payment_time']}")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    img = Image.open(io.BytesIO(photo_bytes))
    text = pytesseract.image_to_string(img, lang='uz+eng')

    if not text.strip():
        await update.message.reply_text("Matn topilmadi.")
        return

    payment_info = await extract_payment_info(text)
    checkmi = await Rahmat_check(update.message, payment_info)

    if not checkmi:
        with open("photos/check.jpg", "rb") as photo:
            await update.message.reply_text(
                "❌ Check noto'g'ri yoki to'liq emas.\n\n"
                "Iltimos, quyidagi namunaga o'xshash to'liq Rahmat check yuboring 👇"
            )
            await update.message.reply_photo(photo)
        return
    else:
        await update.message.reply_text("✅ Check malumotlari tekshirilmoqda...")
        await update.message.reply_text(f"To'lov ma'lumotlari:\nIdentifikator: {payment_info['transaction_id']}\nXizmat: {payment_info['payment_service']}\nSumma: {payment_info['amount']} so'm\nVaqt: {payment_info['payment_time']}")

    payment_time = payment_info['payment_time']
    amount = float(payment_info['amount']) if payment_info['amount'] else 0

    # Firestore collection: payments
    doc_ref = db.collection('payments').document(payment_time)
    doc = doc_ref.get()

    if not doc.exists:
        await update.message.reply_text("❌ Checkingiz Bazada topilmadi.")
        return

    data = doc.to_dict()
    
    # Check used flag
    if data.get('used'):
        await update.message.reply_text("⚠️ Check allaqachon ishlatilgan (used).")
        return

    fb_amount = float(data.get('amount', 0))
    # Summa tekshiruvi: diff < 6%
    if abs(fb_amount - amount)/fb_amount > 0.06:
        await update.message.reply_text("❌ Checkdagi summa FBdagi summa bilan mos emas.")
        return

    # Mijoz yuborgan raqam
    user_phone = payment_info.get('phone')  # Agar OCRdan olish mumkin bo'lsa
    fb_phone = data.get('phone')  # Firestore'da saqlangan 90-636-xx-xx

    if not user_phone or user_phone[-4:] != fb_phone[-4:]:
        await update.message.reply_text("❌ Check sizga tegishli emas.")
        return

    # Hammasi to'g'ri bo'lsa, status success va used=True
    doc_ref.update({
        "used": True,
        "status": "success"
    })

    # Rasmni Storage ga saqlash
    file_name = f"checks/{payment_time.replace(' ', '_')}.jpg"
    blob = bucket.blob(file_name)
    blob.upload_from_string(photo_bytes, content_type='image/jpeg')

    # Xabar yuborish
    await update.message.reply_text(
        f"✅ To'lov tasdiqlandi. Obunangiz faollashdi!\n"
        f"Telefon raqamingiz: {fb_phone}"
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
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    print("Bot ishga tushdi...")
    app.run_polling()


# Firebase ishga tushirish (bitta marta)
cred = credentials.Certificate("firebase_service_account.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'your-bucket-name.appspot.com'
})
