import re, os

from ocr_def_ru import extract_payment_info_ru
from ocr_def_uz import extract_payment_info_uz
from ocr_def_en import extract_payment_info_en

async def Rahmat_check(update, payment_info):
    if not payment_info:
        return False

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
    if not language:
        return None, None

    if language == 'uz':
        return await extract_payment_info_uz(text), language
    elif language == 'ru':
        return await extract_payment_info_ru(text), language
    elif language == 'en':
        return await extract_payment_info_en(text), language