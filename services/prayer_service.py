"""
Namoz vaqtlari xizmati — AlAdhan API
"""
import aiohttp
from datetime import datetime, timedelta
from config import LATITUDE, LONGITUDE, PRAYER_NAMES, TAHAJJUD_MINUTES_BEFORE_FAJR


async def get_prayer_times(date: datetime | None = None) -> dict | None:
    """Bugungi namoz vaqtlarini olish"""
    if date is None:
        date = datetime.now()

    date_str = date.strftime("%d-%m-%Y")
    url = (
        f"https://api.aladhan.com/v1/timings/{date_str}"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&method=3&school=1"  # Muslim World League + Hanafi
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["data"]["timings"]
        return None
    except Exception:
        return None


async def get_formatted_prayer_times() -> str:
    """Namoz vaqtlarini chiroyli formatda qaytarish"""
    timings = await get_prayer_times()
    if not timings:
        return "❌ Namoz vaqtlarini olishda xatolik yuz berdi."

    today = datetime.now().strftime("%d.%m.%Y")
    lines = [f"🕌 *Farg'ona — {today}*\n"]

    for eng_name, uz_name in PRAYER_NAMES.items():
        time_str = timings.get(eng_name, "—")
        # Vaqtdan timezone qismini olib tashlash (masalan: "05:30 (+05)" -> "05:30")
        time_clean = time_str.split(" ")[0] if " " in time_str else time_str
        lines.append(f"{uz_name}: *{time_clean}*")

    # Tahajjud vaqtini hisoblash
    fajr_str = timings.get("Fajr", "").split(" ")[0]
    if fajr_str:
        try:
            fajr_time = datetime.strptime(fajr_str, "%H:%M")
            tahajjud_time = fajr_time - timedelta(minutes=TAHAJJUD_MINUTES_BEFORE_FAJR)
            lines.append(f"\n🌃 Tahajjud vaqti: *{tahajjud_time.strftime('%H:%M')}*")
        except ValueError:
            pass

    # Keyingi namozni aniqlash
    now = datetime.now()
    next_prayer = _get_next_prayer(timings, now)
    if next_prayer:
        name, time_left = next_prayer
        lines.append(f"\n⏳ Keyingi namoz: {name} ({time_left} qoldi)")

    return "\n".join(lines)


def _get_next_prayer(timings: dict, now: datetime) -> tuple[str, str] | None:
    """Keyingi namozni aniqlash"""
    prayer_order = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

    for eng_name in prayer_order:
        time_str = timings.get(eng_name, "").split(" ")[0]
        if not time_str:
            continue
        try:
            prayer_time = now.replace(
                hour=int(time_str.split(":")[0]),
                minute=int(time_str.split(":")[1]),
                second=0,
                microsecond=0,
            )
            if prayer_time > now:
                diff = prayer_time - now
                hours, remainder = divmod(int(diff.total_seconds()), 3600)
                minutes = remainder // 60
                uz_name = PRAYER_NAMES.get(eng_name, eng_name)
                if hours > 0:
                    return uz_name, f"{hours} soat {minutes} daqiqa"
                else:
                    return uz_name, f"{minutes} daqiqa"
        except (ValueError, IndexError):
            continue

    return None


async def get_prayer_schedule(date: datetime | None = None) -> list[dict] | None:
    """Namoz vaqtlarini schedule uchun qaytarish"""
    timings = await get_prayer_times(date)
    if not timings:
        return None

    schedule = []
    prayer_order = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

    for eng_name in prayer_order:
        time_str = timings.get(eng_name, "").split(" ")[0]
        if time_str:
            try:
                hour, minute = map(int, time_str.split(":"))
                uz_name = PRAYER_NAMES.get(eng_name, eng_name)
                schedule.append({
                    "name": uz_name,
                    "eng_name": eng_name,
                    "hour": hour,
                    "minute": minute,
                })
            except (ValueError, IndexError):
                continue

    # Tahajjud qo'shish
    fajr_str = timings.get("Fajr", "").split(" ")[0]
    if fajr_str:
        try:
            fajr_hour, fajr_min = map(int, fajr_str.split(":"))
            fajr_total = fajr_hour * 60 + fajr_min
            tahajjud_total = fajr_total - TAHAJJUD_MINUTES_BEFORE_FAJR
            if tahajjud_total < 0:
                tahajjud_total += 24 * 60
            schedule.insert(0, {
                "name": "🌃 Tahajjud",
                "eng_name": "Tahajjud",
                "hour": tahajjud_total // 60,
                "minute": tahajjud_total % 60,
            })
        except (ValueError, IndexError):
            pass

    return schedule
