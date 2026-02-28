import re, os

from ocr_def_ru import extract_payment_info_ru
from ocr_def_uz import extract_payment_info_uz
from ocr_def_en import extract_payment_info_en

async def Rahmat_check(update, payment_info):

    if not (
        payment_info.get("transaction_id") and
        payment_info.get("amount") and
        payment_info.get("payment_time") and
        payment_info.get("payment_service")
    ):
        return False  # Check noto'g'ri yoki to'liq emas
    return True  # Check to'g'ri va to'liq

async def detect_language(text: str):
    # Oddiy til aniqlash: agar matnda "identifikatori" so'zi bo'lsa, bu o'zbekcha deb hisoblaymiz
    if re.search(r'identifikatori', text, re.IGNORECASE):
        return 'uz'
    # Agar "идентификатор" so'zi bo'lsa, bu ruscha deb hisoblaymiz
    elif re.search(r'оплачен', text, re.IGNORECASE):
        return 'ru'
    # Aks holda, tilni aniqlay olmaymiz
    elif re.search(r'paid', text, re.IGNORECASE):
        return 'en'

    return None

# OCR orqali to'lov ma'lumotlarini ajratib olish
async def extract_payment_info(text: str):
    language = await detect_language(text)

    print(f"Detected language: {language}")  # Tilni tekshirish uchun konsolga chiqaramiz

    if language == 'uz':
        return await extract_payment_info_uz(text), language
    elif language == 'ru':
        return await extract_payment_info_ru(text), language
    elif language == 'en':
        return await extract_payment_info_en(text), language
    return None, None


# # OCR orqali to'lov ma'lumotlarini ajratib olish
# async def extract_payment_info(text: str):
#     # Textni normalize qilamiz
#     clean_text = text.replace("'", "'").replace("`", "'")

#     # Transaction ID (identifikatori yoki id= holatlari uchun)
#     transaction_match = re.search(
#         r'(?:identifikatori)[^\d]*(\d{5,})',
#         clean_text,
#         re.IGNORECASE
#     )
#     transaction_id = transaction_match.group(1) if transaction_match else None

#     # Amount (so'm, som, so m variantlari uchun)
#     amount_match = re.search(
#         r'summasi[^\d]*([\d\s,.]+)',
#         clean_text,
#         re.IGNORECASE
#     )

#     amount = None
#     if amount_match:
#         amount = re.sub(r'[^\d.]', '', amount_match.group(1))

#     # Date / Time
#     time_match = re.search(
#         r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
#         clean_text
#     )
#     payment_time = time_match.group(1) if time_match else None

#     # Payment Service
#     service_match = re.search(
#         r'xizmati[:\s]+([a-z]+)',
#         clean_text,
#         re.IGNORECASE
#     )
#     payment_service = service_match.group(1) if service_match else None

#     return {
#         "transaction_id": transaction_id,
#         "payment_service": payment_service,
#         "amount": amount,
#         "payment_time": payment_time,
#     }