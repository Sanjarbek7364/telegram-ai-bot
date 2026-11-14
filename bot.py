"""
🤖 Telegram AI Agent Bot
Farg'ona uchun — Gemini AI, Namoz vaqtlari, Budilnik, Ovozli xabar
"""
import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from config import TELEGRAM_BOT_TOKEN
from handlers.chat import handle_message, handle_turdim, handle_mode, handle_mode_callback
from handlers.image import handle_image
from handlers.prayer import handle_namoz, handle_namoz_on, handle_namoz_off, setup_prayer_schedule
from handlers.alarm import handle_alarm
from handlers.voice import handle_voice
from handlers.memory import handle_esla, handle_eslatmalar, handle_unut
from services.memory_service import init_db

# Logging sozlash
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start buyrug'i"""
    user_name = update.effective_user.first_name or "do'stim"
    welcome = (
        f"🤖 Assalomu alaykum, {user_name}!\n\n"
        f"Men sizning shaxsiy AI yordamchingizman! 🚀\n\n"
        f"📋 *Nima qila olaman:*\n\n"
        f"💬 *Chatbot* — istalgan savolga javob beraman\n"
        f"🧠 *Rejim* — `/mode` — Flash / 4-Hydrogen / Pro tanlash\n"
        f"🖼 *Rasm* — `/rasm [tavsif]` — rasm yarataman\n"
        f"🕌 *Namoz* — `/namoz` — bugungi vaqtlar\n"
        f"🔔 *Ogohlantirish* — `/namoz_on` — har namozda xabar\n"
        f"⏰ *Budilnik* — `/alarm 05:30` yoki \"3 ga uyg'ot\"\n"
        f"📝 *Eslatma* — `/esla [matn]` — eslab qolaman\n"
        f"🎤 *Ovozli* — ovozli xabar yuboring — matnga o'giraman\n\n"
        f"💡 Menga istalgan narsani yozing — yordam beraman! 😊"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help buyrug'i"""
    help_text = (
        "📖 *Buyruqlar ro'yxati:*\n\n"
        "/start — Botni ishga tushirish\n"
        "/mode — AI modelini tanlash (Flash / Hydrogen / Pro)\n"
        "/namoz — Bugungi namoz vaqtlari\n"
        "/namoz\\_on — Namoz ogohlantirishni yoqish\n"
        "/namoz\\_off — Namoz ogohlantirishni o'chirish\n"
        "/rasm [tavsif] — Rasm yaratish\n"
        "/alarm [HH:MM] — Budilnik qo'yish\n"
        "/esla [matn] — Eslatma saqlash\n"
        "/eslatmalar — Barcha eslatmalar\n"
        "/unut [raqam] — Eslatmani o'chirish\n"
        "/help — Yordam\n\n"
        "💬 *Qo'shimcha:*\n"
        "• Istalgan savolni yozing — AI javob beradi\n"
        "• Ovozli xabar yuboring — matnga o'giraman\n"
        "• \"ertaga 5 ga uyg'ot\" — budilnik qo'yiladi\n"
        "• \"eslab qol: bozorga borish kerak\" — saqlayman\n"
        "• \"turdim\" — ogohlantirishni to'xtatadi"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def post_init(application: Application):
    """Bot ishga tushganda: DB yaratish, buyruqlar, namoz schedule"""
    # Ma'lumotlar bazasini yaratish
    await init_db()
    logger.info("✅ Ma'lumotlar bazasi tayyor.")

    # Bot buyruqlarini o'rnatish
    commands = [
        BotCommand("start", "Botni ishga tushirish"),
        BotCommand("mode", "AI modelini tanlash"),
        BotCommand("help", "Yordam"),
        BotCommand("namoz", "Bugungi namoz vaqtlari"),
        BotCommand("namoz_on", "Namoz ogohlantirishni yoqish"),
        BotCommand("namoz_off", "Namoz ogohlantirishni o'chirish"),
        BotCommand("rasm", "Rasm yaratish"),
        BotCommand("alarm", "Budilnik qo'yish"),
        BotCommand("esla", "Eslatma saqlash"),
        BotCommand("eslatmalar", "Barcha eslatmalar"),
        BotCommand("unut", "Eslatmani o'chirish"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Bot buyruqlari o'rnatildi.")

    # Namoz scheduleni o'rnatish
    await setup_prayer_schedule(application)
    logger.info("✅ Namoz schedule o'rnatildi.")


def main():
    """Botni ishga tushirish"""
    logger.info("🚀 Bot ishga tushmoqda...")

    # Application yaratish
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # === HANDLERS ===

    # Buyruqlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mode", handle_mode))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("namoz", handle_namoz))
    app.add_handler(CommandHandler("namoz_on", handle_namoz_on))
    app.add_handler(CommandHandler("namoz_off", handle_namoz_off))
    app.add_handler(CommandHandler("rasm", handle_image))
    app.add_handler(CommandHandler("alarm", handle_alarm))
    app.add_handler(CommandHandler("esla", handle_esla))
    app.add_handler(CommandHandler("eslatmalar", handle_eslatmalar))
    app.add_handler(CommandHandler("unut", handle_unut))

    # Inline tugmalar callback handler
    app.add_handler(CallbackQueryHandler(handle_mode_callback, pattern=r"^set_mode_"))

    # Ovozli xabar
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # "Turdim" — ogohlantirishlarni to'xtatish (umumiy xabar handlerdan OLDIN)
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r"(?i)(turdim|turibman|turaman|uyg.ondim)"),
            handle_turdim,
        )
    )

    # Umumiy matn — AI chatbot (eng oxirgi)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Botni ishga tushirish
    logger.info("✅ Bot tayyor! Polling boshlandi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
