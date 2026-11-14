"""
Namoz vaqtlari handler
"""
import logging
from datetime import datetime, time as dt_time
from telegram import Update
from telegram.ext import ContextTypes
from services.prayer_service import get_formatted_prayer_times, get_prayer_schedule
from services.memory_service import (
    ensure_user, set_prayer_notify, get_prayer_notify, get_prayer_subscribers
)
from config import ALERT_INTERVAL_SECONDS, get_now, UZB_TZ

logger = logging.getLogger(__name__)


async def handle_namoz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/namoz — bugungi namoz vaqtlarini ko'rsatish"""
    await ensure_user(update.effective_user.id, update.effective_user.first_name or "")
    text = await get_formatted_prayer_times()
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_namoz_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/namoz_on — namoz ogohlantirishni yoqish"""
    user_id = update.effective_user.id
    await ensure_user(user_id, update.effective_user.first_name or "")
    await set_prayer_notify(user_id, True)

    # Bugungi namoz scheduleni o'rnatish
    await _schedule_today_prayers(context, user_id, update.effective_chat.id)

    await update.message.reply_text(
        "✅ Namoz ogohlantirish yoqildi!\n\n"
        "🕌 Har bir namoz vaqtida xabar olasiz.\n"
        "🌃 Tahajjud vaqtida ham ogohlantirilasiz.\n"
        "💡 O'chirish: /namoz_off\n\n"
        "Namoz o'qiganingizda \"turdim\" deb yozing — to'xtaydi."
    )


async def handle_namoz_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/namoz_off — namoz ogohlantirishni o'chirish"""
    user_id = update.effective_user.id
    await set_prayer_notify(user_id, False)

    # Bu foydalanuvchi uchun barcha namoz joblarini o'chirish
    _remove_prayer_jobs(context, user_id)

    await update.message.reply_text("🔕 Namoz ogohlantirish o'chirildi.")


async def setup_prayer_schedule(app):
    """Bot ishga tushganda barcha obunachilarga namoz scheduleni o'rnatish"""
    try:
        subscribers = await get_prayer_subscribers()
        for user_id in subscribers:
            await _schedule_today_prayers(app, user_id, user_id)
        logger.info(f"Namoz schedule {len(subscribers)} ta foydalanuvchi uchun o'rnatildi.")
    except Exception as e:
        logger.error(f"Namoz schedule xatolik: {e}")

    # Har kuni yarim tunda ertangi schedule'ni yangilash (O'zbekiston vaqti bilan 00:05 da)
    try:
        app.job_queue.run_daily(
            _daily_prayer_reschedule,
            time=dt_time(0, 5, 0, tzinfo=UZB_TZ),
            name="daily_prayer_reschedule",
        )
    except AttributeError:
        # app ning job_queue attributi yo'q bo'lsa (context orqali kelganda)
        pass


async def _schedule_today_prayers(context_or_app, user_id: int, chat_id: int):
    """Bugungi namoz vaqtlari uchun joblar o'rnatish"""
    schedule = await get_prayer_schedule()
    if not schedule:
        return

    now = get_now()

    # Avvalgi joblarni tozalash
    try:
        job_queue = context_or_app.job_queue
    except AttributeError:
        job_queue = context_or_app

    _remove_prayer_jobs_by_queue(job_queue, user_id)

    for prayer in schedule:
        prayer_time = now.replace(
            hour=prayer["hour"], minute=prayer["minute"], second=0, microsecond=0
        )

        # Faqat kelajakdagi namozlarni schedule qilish
        if prayer_time <= now:
            continue

        delay = (prayer_time - now).total_seconds()
        job_queue.run_once(
            _prayer_alert_callback,
            when=delay,
            data={
                "chat_id": chat_id,
                "user_id": user_id,
                "prayer_name": prayer["name"],
            },
            name=f"prayer_{user_id}_{prayer['eng_name']}",
        )


async def _prayer_alert_callback(context: ContextTypes.DEFAULT_TYPE):
    """Namoz vaqti keldi — xabar yuborish"""
    data = context.job.data
    chat_id = data["chat_id"]
    user_id = data["user_id"]
    prayer_name = data["prayer_name"]

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🕌 {prayer_name} vaqti bo'ldi!\n\n"
            f"Namoz o'qib oling! Allah qabul qilsin! 🤲\n\n"
            f"💡 O'qiganingizda \"turdim\" deb yozing."
        ),
    )

    # Har 30 soniyada eslatish
    context.job_queue.run_repeating(
        _prayer_repeating_alert,
        interval=ALERT_INTERVAL_SECONDS,
        first=ALERT_INTERVAL_SECONDS,
        data={
            "chat_id": chat_id,
            "user_id": user_id,
            "prayer_name": prayer_name,
            "count": 0,
        },
        name=f"alert_{user_id}",
    )


async def _prayer_repeating_alert(context: ContextTypes.DEFAULT_TYPE):
    """Namoz eslatmasi — turganicha takror"""
    data = context.job.data
    chat_id = data["chat_id"]
    prayer_name = data["prayer_name"]
    data["count"] = data.get("count", 0) + 1
    count = data["count"]

    messages = [
        f"🕌 {prayer_name} — hali namoz o'qimadingizmi? Shoshiling!",
        f"🔔 {prayer_name} vaqti o'tib ketyapti! Namoz o'qing!",
        f"🤲 {prayer_name} — Allah sizi kutmoqda! Turing!",
        f"⏰ {prayer_name}! Namozingiz qolmasin!",
        f"🕌 {prayer_name}! 'turdim' deb yozing!",
    ]
    await context.bot.send_message(
        chat_id=chat_id, text=messages[count % len(messages)]
    )


async def _daily_prayer_reschedule(context: ContextTypes.DEFAULT_TYPE):
    """Har kuni yangi schedule o'rnatish"""
    try:
        subscribers = await get_prayer_subscribers()
        for user_id in subscribers:
            await _schedule_today_prayers(context, user_id, user_id)
        logger.info(f"Kunlik namoz schedule yangilandi: {len(subscribers)} foydalanuvchi.")
    except Exception as e:
        logger.error(f"Kunlik namoz yangilash xatolik: {e}")


def _remove_prayer_jobs(context, user_id: int):
    """Foydalanuvchining barcha namoz joblarini o'chirish"""
    try:
        job_queue = context.job_queue
    except AttributeError:
        job_queue = context
    _remove_prayer_jobs_by_queue(job_queue, user_id)


def _remove_prayer_jobs_by_queue(job_queue, user_id: int):
    """Job queue dan namoz joblarini o'chirish"""
    prefixes = [
        f"prayer_{user_id}_",
        f"alert_{user_id}",
    ]
    for job in job_queue.jobs():
        if job.name and any(job.name.startswith(p) for p in prefixes):
            job.schedule_removal()
