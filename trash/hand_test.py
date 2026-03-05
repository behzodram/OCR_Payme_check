from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import *

WAIT_PHONE = 1


# 1️⃣ RASM + CAPTION QABUL QILISH
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption:
        await update.message.reply_text(
            "❌ Rasm izoh (caption) bilan yuborilishi kerak."
        )
        return ConversationHandler.END

    caption_text = update.message.caption.strip()

    # Caption ichidagi raqamni saqlaymiz
    context.user_data["caption_text"] = caption_text

    await update.message.reply_text(
        "📸 Rasm va izoh qabul qilindi.\n"
        "📱 Endi telefon raqamingizni kiriting:"
    )

    return WAIT_PHONE


# 2️⃣ TELEFONNI TEKSHIRISH
async def phone_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_phone = update.message.text.strip()
    caption_text = context.user_data.get("caption_text")

    if not caption_text:
        await update.message.reply_text("❌ Caption topilmadi.")
        return ConversationHandler.END

    # Oddiy taqqoslash (caption ichida telefon mavjudligini tekshiramiz)
    if user_phone in caption_text:
        await update.message.reply_text("✅ Mos keldi.")
    else:
        await update.message.reply_text("❌ Mos kelmadi.")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, photo_handler)],
        states={
            WAIT_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_check_handler)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == "__main__":
    main()