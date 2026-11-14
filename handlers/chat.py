"""
AI Chat handler — Gemini bilan suhbat
"""
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from services.gemini_service import (
    generate_response, analyze_with_context, AVAILABLE_MODELS, get_user_mode, set_user_mode
)
from services.memory_service import (
    ensure_user, save_conversation, get_all_memories_text, add_memory
)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oddiy matnli xabarlarni qayta ishlash"""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id
    message = update.message.text.strip()

    # Foydalanuvchini bazaga qo'shish
    await ensure_user(user_id, user.first_name or "", user.username or "")

    # Budilnik so'rovi tekshirish ("ertaga 3 ga uyg'ot", "5:30 da uyg'ot")
    alarm_result = _parse_alarm_request(message)
    if alarm_result:
        target_time, description = alarm_result
        await _set_alarm(update, context, target_time, description)
        return

    # Eslatma so'rovi tekshirish ("eslab qol: ...", "esla: ...")
    memory_match = re.match(
        r"(?:eslab?\s*qol|esla|yodda\s*tut|saqlab?\s*qo['\u2019]?y)[:\s]+(.+)",
        message,
        re.IGNORECASE,
    )
    if memory_match:
        content = memory_match.group(1).strip()
        await add_memory(user_id, content)
        await update.message.reply_text(f"✅ Eslatma saqlandi: {content}")
        return

    # "Typing..." ko'rsatish
    await update.message.chat.send_action("typing")

    # Eslatmalar kontekstini olish
    memories = await get_all_memories_text(user_id)

    # Gemini'dan javob olish
    if memories:
        response = await analyze_with_context(user_id, message, memories)
    else:
        response = await generate_response(user_id, message)

    # Suhbatni saqlash
    await save_conversation(user_id, "user", message)
    await save_conversation(user_id, "assistant", response)

    # Javob yuborish (uzun bo'lsa bo'laklarga bo'lish)
    if len(response) > 4096:
        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i : i + 4096])
    else:
        await update.message.reply_text(response)


async def handle_turdim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'Turdim' xabarini qayta ishlash — barcha ogohlantirishlarni to'xtatish"""
    user_id = update.effective_user.id

    # Bu foydalanuvchi uchun barcha takroriy joblarni o'chirish
    jobs_removed = 0
    current_jobs = context.job_queue.get_jobs_by_name(f"alert_{user_id}")
    for job in current_jobs:
        job.schedule_removal()
        jobs_removed += 1

    if jobs_removed > 0:
        await update.message.reply_text(
            "✅ Xayrli tong! Barcha ogohlantirishlar to'xtatildi. Allah qabul qilsin! 🤲"
        )
    else:
        await update.message.reply_text("😊 Hech qanday faol ogohlantirish yo'q.")


async def handle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/mode — AI modelini tanlash menyusi"""
    user_id = update.effective_user.id
    current_mode = get_user_mode(user_id)

    keyboard = []
    for key, data in AVAILABLE_MODELS.items():
        prefix = "✅ " if key == current_mode else "▫️ "
        button_text = f"{prefix}{data['name']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"set_mode_{key}")])

    markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🤖 *AI Modelini tanlang:*\n\n"
        "⚡ *Gemini 3.8 Flash:* Juda tezkor javoblar (kundalik suhbat, eslatma, namoz).\n"
        "🧠 *Gemini 4 Hydrogen:* Chuqur aql, eng kuchli mantiq (kod yozish, elektronika sxemalari, fizika).\n"
        "💎 *Gemini Pro:* Kuchli va barqaror aql.\n\n"
        f"🎯 Hozirgi tanlangan rejim: *{AVAILABLE_MODELS.get(current_mode, {}).get('name', 'Noma''lum')}*"
    )
    await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def handle_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline tugma orqali modelni almashtirish"""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data or not data.startswith("set_mode_"):
        return

    mode_key = data.replace("set_mode_", "")
    user_id = update.effective_user.id

    if set_user_mode(user_id, mode_key):
        model_info = AVAILABLE_MODELS.get(mode_key, {})
        new_name = model_info.get("name", mode_key)

        keyboard = []
        for key, mdata in AVAILABLE_MODELS.items():
            prefix = "✅ " if key == mode_key else "▫️ "
            keyboard.append([InlineKeyboardButton(f"{prefix}{mdata['name']}", callback_data=f"set_mode_{key}")])
        markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎉 AI Rejimi muvaffaqiyatli o'zgartirildi!\n\n"
            f"🎯 Faol model: *{new_name}*\n"
            f"ℹ️ {model_info.get('desc', '')}\n\n"
            f"Endi bemalol xabar yozishingiz mumkin! 🚀✨",
            reply_markup=markup,
            parse_mode="Markdown",
        )


def _parse_alarm_request(message: str) -> tuple[datetime, str] | None:
    """Xabardan budilnik vaqtini ajratib olish"""
    msg = message.lower()
    now = datetime.now()

    # "ertaga soat 3 ga uyg'ot" / "ertaga 3:00 da uyg'ot"
    match = re.search(
        r"(ertaga|bugun)?\s*(?:soat\s*)?(\d{1,2})(?::(\d{2}))?\s*(?:ga|da)?\s*"
        r"(uyg['\u2019]?ot|turg['\u2019]?iz|ogohlantir|eslatib\s*qo['\u2019]?y|budilnik)",
        msg,
    )
    if not match:
        # Teskari tartib: "uyg'ot 3 da"
        match = re.search(
            r"(uyg['\u2019]?ot|turg['\u2019]?iz|ogohlantir|budilnik)\w*\s*"
            r"(?:ertaga|bugun)?\s*(?:soat\s*)?(\d{1,2})(?::(\d{2}))?\s*(?:ga|da)?",
            msg,
        )
        if match:
            # Guruhlarni qayta tartiblash
            hour = int(match.group(2))
            minute = int(match.group(3)) if match.group(3) else 0
            is_tomorrow = "ertaga" in msg
        else:
            return None
    else:
        is_tomorrow = match.group(1) == "ertaga" if match.group(1) else False
        hour = int(match.group(2))
        minute = int(match.group(3)) if match.group(3) else 0

    # Vaqtni hisoblash
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if is_tomorrow or target <= now:
        target += timedelta(days=1)

    description = f"⏰ Budilnik: {target.strftime('%H:%M')} ({('ertaga' if is_tomorrow else 'bugun')})"
    return target, description


async def _set_alarm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_time: datetime,
    description: str,
):
    """Budilnik o'rnatish"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    now = datetime.now()
    delay = (target_time - now).total_seconds()

    if delay <= 0:
        await update.message.reply_text("❌ Bu vaqt allaqachon o'tgan!")
        return

    # Bir martalik job — vaqt kelganda ishga tushadi
    context.job_queue.run_once(
        _alarm_callback,
        when=delay,
        data={"chat_id": chat_id, "user_id": user_id},
        name=f"alarm_once_{user_id}_{int(target_time.timestamp())}",
    )

    hours_left = int(delay // 3600)
    mins_left = int((delay % 3600) // 60)
    await update.message.reply_text(
        f"✅ {description}\n"
        f"⏳ {hours_left} soat {mins_left} daqiqa qoldi\n\n"
        f"💡 Uyg'onganingizda \"turdim\" deb yozing — to'xtaydi."
    )


async def _alarm_callback(context: ContextTypes.DEFAULT_TYPE):
    """Budilnik ishlashi — turguncha xabar yozadi"""
    data = context.job.data
    chat_id = data["chat_id"]
    user_id = data["user_id"]

    await context.bot.send_message(
        chat_id=chat_id,
        text="⏰🔔 UYҒONING! Budilnik ishlayapti!\n\nTo'xtatish uchun \"turdim\" deb yozing!",
    )

    # Har 30 soniyada takroriy xabar
    context.job_queue.run_repeating(
        _repeating_alarm,
        interval=30,
        first=30,
        data={"chat_id": chat_id, "user_id": user_id, "count": 0},
        name=f"alert_{user_id}",
    )


async def _repeating_alarm(context: ContextTypes.DEFAULT_TYPE):
    """Har 30 soniyada xabar yuborish"""
    data = context.job.data
    chat_id = data["chat_id"]
    data["count"] = data.get("count", 0) + 1
    count = data["count"]

    messages = [
        "⏰ Hali uxlayapsizmi?! Turing!!! 😤",
        "🔔🔔🔔 TURINGGG!!! Vaqt bo'ldi!",
        "⏰ Turing turing turing!!! 🏃‍♂️",
        "😴➡️😃 Turing! Yangi kun boshlanmoqda!",
        "🔔 Hoy! Turing! 'turdim' deb yozing!",
        "⏰ Budilnik hali ham ishlayapti! TURING! 💪",
    ]
    msg = messages[count % len(messages)]
    await context.bot.send_message(chat_id=chat_id, text=msg)
