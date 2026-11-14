"""
Eslatma (memory) handler — /esla, /eslatmalar, /unut
"""
from telegram import Update
from telegram.ext import ContextTypes
from services.memory_service import (
    ensure_user, add_memory, get_memories, delete_memory
)


async def handle_esla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/esla [matn] — eslatma saqlash"""
    user_id = update.effective_user.id
    await ensure_user(user_id, update.effective_user.first_name or "")

    if not context.args:
        await update.message.reply_text(
            "📝 Eslatma saqlash:\n"
            "`/esla Dushanbaga uchrashuv bor`\n"
            "`/esla Bozordan non olish kerak`\n\n"
            "Yoki shunchaki yozing:\n"
            "\"eslab qol: dushanbaga uchrashuv bor\"",
            parse_mode="Markdown",
        )
        return

    content = " ".join(context.args)
    memory_id = await add_memory(user_id, content)

    await update.message.reply_text(
        f"✅ Eslatma #{memory_id} saqlandi!\n\n"
        f"📝 {content}\n\n"
        f"📋 Barcha eslatmalar: /eslatmalar"
    )


async def handle_eslatmalar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/eslatmalar — barcha eslatmalarni ko'rsatish"""
    user_id = update.effective_user.id
    memories = await get_memories(user_id)

    if not memories:
        await update.message.reply_text(
            "📭 Hali eslatmalar yo'q.\n\n"
            "Qo'shish: `/esla [matn]`",
            parse_mode="Markdown",
        )
        return

    lines = ["📋 *Sizning eslatmalaringiz:*\n"]
    for m in memories:
        lines.append(f"  #{m['id']} — {m['content']}")

    lines.append(f"\n📊 Jami: {len(memories)} ta")
    lines.append("🗑 O'chirish: `/unut [raqam]`")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_unut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/unut [id] — eslatmani o'chirish"""
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "🗑 Eslatmani o'chirish:\n`/unut 1`\n\n"
            "Avval /eslatmalar bilan raqamini ko'ring.",
            parse_mode="Markdown",
        )
        return

    try:
        memory_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Raqam kiriting. Masalan: `/unut 3`", parse_mode="Markdown")
        return

    success = await delete_memory(user_id, memory_id)
    if success:
        await update.message.reply_text(f"✅ Eslatma #{memory_id} o'chirildi.")
    else:
        await update.message.reply_text(f"❌ Eslatma #{memory_id} topilmadi.")
