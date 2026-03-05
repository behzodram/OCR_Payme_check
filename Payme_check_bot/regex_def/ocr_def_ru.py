import re, os

# OCR orqali to'lov ma'lumotlarini ajratib olish
async def extract_payment_info_ru(text: str):    
    # 1️⃣ Transaction ID (ID платежа)
    clean_text = text.replace("'", "'").replace("`", "'")
    
    transaction_match = re.search(
        r'ID\s*платежа[:\s]*([0-9]{5,})',
        clean_text,
        re.IGNORECASE
    )
    transaction_id = transaction_match.group(1) if transaction_match else None

    # 2️⃣ Amount (Сумма оплаты)
    amount_match = re.search(
        r'Сумма\s*оплаты[:\s]*([\d\s]+)',
        clean_text,
        re.IGNORECASE
    )

    amount = None
    if amount_match:
        amount = re.sub(r'\D', '', amount_match.group(1))  # faqat raqam

    # 3️⃣ Sana va vaqtni alohida olib, birlashtiramiz
    date_match = re.search(
        r'(\d{4}-\d{2}-\d{2})',
        clean_text
    )

    time_match = re.search(
        r'(\d{2}:\d{2}:\d{2})',
        clean_text
    )

    payment_time = None
    if date_match and time_match:
        payment_time = f"{date_match.group(1)} {time_match.group(1)}"

    # 4️⃣ Payment Service (Платежный сервис)
    service_match = re.search(
        r'Платежный\s*сервис[:\s]*([А-Яа-яA-Za-z]+)',
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