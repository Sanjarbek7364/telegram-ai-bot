"""
Rasm generatsiya handler
"""
from telegram import Update
from telegram.ext import ContextTypes
from services.gemini_service import generate_image


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/rasm buyrug'i — rasm yaratish"""
    if not context.args:
        await update.message.reply_text(
            "🖼 Rasm yaratish uchun tavsif yozing:\n"
            "Masalan: `/rasm chiroyli tog'lar va ko'l`",
            parse_mode="Markdown",
        )
        return

    prompt = " ".join(context.args)
    await update.message.reply_text(f"🎨 Rasm yaratilmoqda: _{prompt}_...", parse_mode="Markdown")
    await update.message.chat.send_action("upload_photo")

    image_path = await generate_image(prompt)

    if image_path:
        try:
            with open(image_path, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=f"🖼 {prompt}",
                )
            # Temp faylni o'chirish
            import os
            os.remove(image_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Rasmni yuborishda xatolik: {e}")
    else:
        await update.message.reply_text("❌ Rasm yaratib bo'lmadi. Qaytadan urinib ko'ring.")
