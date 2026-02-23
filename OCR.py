# ocr.py
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import pytesseract
from config import BOT_TOKEN, BOT_USERNAME
import io, re
import datetime
import firebase_admin
from firebase_admin import credentials, firestore, storage

# Commands fayldan import qilamiz
from commands import start, stats, help_command, share

# Logger
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

def initialize_firebase():
    try:
        # Firebase sozlamalari
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        SERVICE_ACCOUNT_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        
        firebase_admin.initialize_app(cred, {
            'storageBucket': STORAGE_BUCKET
        })

        db = firestore.client()
        bucket = storage.bucket()

        logging.info("Firebase initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing Firebase: {e}")

# OCR orqali to‘lov ma’lumotlarini ajratib olish
async def extract_payment_info(text: str):
    # Textni normalize qilamiz
    clean_text = text.replace("’", "'").replace("`", "'")

    # Transaction ID (identifikatori yoki id= holatlari uchun)
    transaction_match = re.search(
        r'(?:identifikatori|id)[^\d]*(\d{5,})',
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
        "amount": amount,
        "payment_time": payment_time,
        "payment_service": payment_service
    }

# Rasmni qabul qilish va Tesseract OCR

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    img = Image.open(io.BytesIO(photo_bytes))

    text = pytesseract.image_to_string(img, lang='uz+eng')
    transaction_id, amount, payment_time, payment_service = await extract_payment_info(text)

    if not transaction_id:
        await update.message.reply_text("Transaction ID topilmadi. Iltimos checkni qayta yuboring.")
        return

    # Firestore check: agar mavjud bo'lsa ogohlantirish
    doc_ref = db.collection("payments").document(transaction_id)
    doc = doc_ref.get()
    if doc.exists:
        await update.message.reply_text(
            f"Transaction ID band, iltimos checkni 1 marta jo'nating. \n\nAgar muammo bo'lsa, admin bilan bog'laning.\nBot username: @{BOT_USERNAME}"
        )
        return

    created_at = datetime.datetime.utcnow().isoformat()

    doc_ref.set({
        "transaction_id": transaction_id,
        "amount": amount,
        "payment_time": payment_time,
        "payment_service": payment_service,
        "created_at": created_at,
        "status": "pending",
        "user_id": str(update.effective_user.id),
        "phone1": "none",
        "used": False
    })

    # Firebase Storage
    blob = bucket.blob(f"payments/{transaction_id}/screenshot.png")
    blob.upload_from_string(photo_bytes, content_type='image/png')
    blob.metadata = {"created_at": created_at}
    blob.patch()

    await update.message.reply_text(
        f"To‘lov saqlandi:\nTransaction ID: {transaction_id}\nAmount: {amount} so'm\n"
        f"Payment Time: {payment_time}\nService: {payment_service}\n\n"
        f"Admin panel orqali tekshirilishi mumkin."
    )

# Bot ishga tushurish
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    initialize_firebase()

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
