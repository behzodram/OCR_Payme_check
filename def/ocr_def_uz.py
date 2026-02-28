import re, os

# OCR orqali to'lov ma'lumotlarini ajratib olish
async def extract_payment_info_uz(text: str):
    # Textni normalize qilamiz
    clean_text = text.replace("'", "'").replace("`", "'")

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