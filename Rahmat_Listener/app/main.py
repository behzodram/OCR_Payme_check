import re
import os
import asyncio
from telethon import TelegramClient, events
import firebase_admin
from firebase_admin import credentials, firestore

from config import API_ID, API_HASH

# ===============================
# 🔥 FIREBASE INIT
# ===============================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_KEY_PATH = os.path.join(BASE_DIR, "..", "..", "serviceAccountKey.json")
SERVICE_KEY_PATH = os.path.abspath(SERVICE_KEY_PATH)

cred = credentials.Certificate(SERVICE_KEY_PATH)
firebase_admin.initialize_app(cred)

db = firestore.client()

client = TelegramClient(
    "Rahmat",
    API_ID,
    API_HASH,
    device_model="AWS LINUX/OCR_Payme_Check",
    system_version="Windows 10",
    app_version="Rahmat bot Listener -> Firebase 1.0"
)


# 🎯 Target bot username
TARGET_BOT = "RahmatRobot"
# ===============================
# 📌 REGEX
# ===============================

pattern = re.compile(
    r"Телефон:\s*(\+998\d+).*?"
    r"Сумма:\s*([\d\s,]+)\s*сум.*?"
    r"Дата:\s*([\d\-:\s]+)",
    re.DOTALL
)

# ===============================
# 🧠 UNIQUE TIME ID GENERATOR
# ===============================

async def generate_unique_doc_id(base_time):
    collection = db.collection("payments")

    # Birinchi urinish
    doc_ref = collection.document(base_time)
    if not doc_ref.get().exists:
        return base_time

    # Agar mavjud bo‘lsa suffix qo‘shamiz
    counter = 2
    while True:
        new_id = f"{base_time}:__ID__{counter}"
        doc_ref = collection.document(new_id)
        if not doc_ref.get().exists:
            return new_id
        counter += 1

# ===============================
# 📥 TELEGRAM LISTENER
# ===============================

@client.on(events.NewMessage(from_users=TARGET_BOT))
async def handler(event):
    text = event.raw_text

    if "💼 Локация:" in text and "💵 Сумма:" in text:
        match = pattern.search(text)

        if match:
            phone = match.group(1)
            amount_raw = match.group(2)
            date = match.group(3).strip()

            amount = float(
                amount_raw.replace(" ", "").replace(",", ".")
            )

            # 🔐 Unique doc id yaratamiz
            doc_id = await generate_unique_doc_id(date)

            # 🔥 Firestore ga yozamiz
            db.collection("payments").document(doc_id).set({
                "phone": phone,
                "amount": amount,
                "date": date,
                "status": "pending",
                "used": False
            })

            print("✅ FIREBASE GA YOZILDI:", doc_id)

# ===============================
# ▶️ RUN
# ===============================

async def main():
    await client.start()
    print("👂 Listening RahmatRobot + Firebase connected...")
    await client.run_until_disconnected()

asyncio.run(main())