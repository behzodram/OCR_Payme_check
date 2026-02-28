import re, os

# OCR orqali to'lov ma'lumotlarini ajratib olish (EN version)
async def extract_payment_info_en(text: str):

    clean_text = text.replace("'", "'").replace("`", "'")

    # 1️⃣ Payment ID
    transaction_match = re.search(
        r'Payment\s*ID[:\s]*([0-9]{5,})',
        clean_text,
        re.IGNORECASE
    )
    transaction_id = transaction_match.group(1) if transaction_match else None

    # 2️⃣ Payment service
    service_match = re.search(
        r'Payment\s*service[:\s]*([A-Za-z]+)',
        clean_text,
        re.IGNORECASE
    )
    payment_service = service_match.group(1) if service_match else None

    # 3️⃣ Payment amount
    amount_match = re.search(
        r'Payment\s*amount[:\s]*([\d\s]+)',
        clean_text,
        re.IGNORECASE
    )

    amount = None
    if amount_match:
        amount = re.sub(r'\D', '', amount_match.group(1))  # faqat raqam

    # 4️⃣ Payment time (YYYY-MM-DD HH:MM:SS)
    time_match = re.search(
        r'Payment\s*time[:\s]*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
        clean_text,
        re.IGNORECASE
    )
    payment_time = time_match.group(1) if time_match else None

    return {
        "transaction_id": transaction_id,
        "payment_service": payment_service,
        "amount": amount,
        "payment_time": payment_time,
    }