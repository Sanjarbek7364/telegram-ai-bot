"""
Budilnik handler — /alarm buyrug'i
"""
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from config import get_now


async def handle_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/alarm HH:MM — budilnik qo'yish"""
    if not context.args:
        await update.message.reply_text(
            "⏰ Budilnik qo'yish:\n"
            "`/alarm 05:30` — bugun/ertaga 5:30 da\n"
            "`/alarm 15:00` — 15:00 da\n\n"
            "Yoki shunchaki yozing:\n"
            "\"ertaga soat 3 ga uyg'ot\"",
            parse_mode="Markdown",
        )
        return

    time_str = context.args[0]

    try:
        hour, minute = map(int, time_str.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Noto'g'ri format. Masalan: `/alarm 05:30`",
            parse_mode="Markdown",
        )
        return

    now = get_now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Agar vaqt o'tgan bo'lsa, ertaga
    is_tomorrow = False
    if target <= now:
        target += timedelta(days=1)
        is_tomorrow = True

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    delay = (target - now).total_seconds()

    # Bir martalik budilnik
    context.job_queue.run_once(
        _alarm_fire,
        when=delay,
        data={"chat_id": chat_id, "user_id": user_id, "time": time_str},
        name=f"alarm_once_{user_id}_{int(target.timestamp())}",
    )

    day_text = "ertaga" if is_tomorrow else "bugun"
    hours_left = int(delay // 3600)
    mins_left = int((delay % 3600) // 60)

    await update.message.reply_text(
        f"✅ Budilnik o'rnatildi: {time_str} ({day_text})\n"
        f"⏳ {hours_left} soat {mins_left} daqiqa qoldi\n\n"
        f"💡 Uyg'onganingizda \"turdim\" deb yozing!"
    )


async def _alarm_fire(context: ContextTypes.DEFAULT_TYPE):
    """Budilnik ishlashi"""
    data = context.job.data
    chat_id = data["chat_id"]
    user_id = data["user_id"]

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "⏰🔔🔔🔔 BUDILNIK!!!\n\n"
            "Turing! Vaqt bo'ldi!\n\n"
            "\"turdim\" deb yozing — to'xtataman!"
        ),
    )

    # Takroriy xabar — har 30 soniyada
    context.job_queue.run_repeating(
        _alarm_repeat,
        interval=30,
        first=30,
        data={"chat_id": chat_id, "user_id": user_id, "count": 0},
        name=f"alert_{user_id}",
    )


async def _alarm_repeat(context: ContextTypes.DEFAULT_TYPE):
    """Takroriy ogohlantirish"""
    data = context.job.data
    chat_id = data["chat_id"]
    data["count"] = data.get("count", 0) + 1
    count = data["count"]

    messages = [
        "⏰ TURING!!! Budilnik hali ishlayapti!",
        "🔔 Hoy! Uxlayapsizmi?! TURING!!!",
        "⏰💪 Turing! Yangi kun! Yangi imkoniyatlar!",
        "🔔🔔 TURIIIING!!! 'turdim' deb yozing!",
        "⏰ Yana uxlab qoldingizmi?! TURING!!!",
        "🏃‍♂️ Turing turing turing!!! Vaqt kutmaydi!",
    ]
    await context.bot.send_message(
        chat_id=chat_id, text=messages[count % len(messages)]
    )
