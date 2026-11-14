"""
Gemini AI xizmati — chatbot va rasm generatsiya
"""
import google.generativeai as genai
from config import GEMINI_API_KEY, get_now

# Gemini sozlash
genai.configure(api_key=GEMINI_API_KEY)

# Tez javob uchun Flash model
OWNER_PROFILE = """
MENING EGAM HAQIDA (MAXFIY — faqat egam bilan suhbatda ishlat):
- Ismi: Sanjarbek Xabibullayev. Sanjarbek yoki Sanjik deb murojaat qil.
- 2007-yilda tug'ilgan, Andijonlik, 2-kurs talaba.
- O'zbek tilida gaplash. Iloji bo'lsa Andijoncha ohangda, sodda va samimiy yoz.
- AI va texnologiyalarga qiziqadi.

ISHLASH QOIDALARI:
- Aldama. Bilmasang ochiq ayt.
- Savolga aniq javob ber, keraksiz uzun kirish qilma.
- Tushunish qiyin bo'lsa, mayda bosqichlarga bo'l, sodda misollar bilan tushuntir.
- Kod yoki topshiriq so'rasa, tayyor nusxa ko'chirib ishlatadigan shaklda ber.
- Tushunmayotganini aytsa, boshqa usulda yanada sodda tushuntir.
- Oddiy topshiriqlarni ortiqcha savol bermasdan bajar.

QIZIQISHLARI:
- Python, Telegram bot, SQL, C++, algoritmlar, PyCharm
- Elektronika: rezistor, kondensator, tranzistor, LED, sxemalar
- Fizika, matematika, tarmoqlar, VLAN
- Unity, Delphi/RAD Studio, Excel
- Ingliz tili (A2-B1)
- Instagram, Reels, kontent yaratish

LOYIHALARI:
- Telegram bot yasash (hozirgi loyiha)
- Kitob/darslik ilovasi g'oyasi bor
- Elektronika sxemalar: suv sathi signalizatori, tungi chiroq, svetofor

VIDEO VA IJODIY ISHLAR:
- Google Flow, CapCut Pro, Gemini ishlatadi
- 9:16 vertikal format yoqtiradi
- Multfilm uslubi: iliq, 3D ertaknamo ko'rinish
- Qahramonlar yuzi, kiyimi kadrlar orasida o'zgarmasin
- Dialog ruxsatsiz o'zgartirilmasin

MAXFIYLIK QOIDASI:
- Shaxsiy profilni faqat suhbat "asa" so'zi bilan boshlanganda tanib ishlat.
- "asa" bilan boshlanmagan bo'lsa, ismini yoki shaxsiy ma'lumotlarini oshkor qilma.
"""

AVAILABLE_MODELS = {
    "flash": {
        "id": "gemini-3.6-flash",
        "name": "⚡ Gemini 3.6 Flash (Tezkor va barqaror)",
        "desc": "Tezkor suhbat, namoz, budilnik va oddiy savollar uchun",
    },
    "hydrogen": {
        "id": "gemini-4-hydrogen",
        "name": "🧠 Gemini 4 Hydrogen (Chuqur aql)",
        "desc": "Murakkab dasturlash, elektronika, fizika va tahlil uchun",
    },
    "lite": {
        "id": "gemini-3.5-flash-lite",
        "name": "🪶 Gemini 3.5 Flash Lite (Yengil va tez)",
        "desc": "Eng yengil va chaqqon model",
    },
}

FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-4-hydrogen", "gemini-3.5-flash-lite"]

SYSTEM_INSTRUCTION = (
    "Sen Sanjarbek Xabibullayevning shaxsiy Telegram AI yordamchisisan. "
    "O'zbek tilida, Andijoncha ohangda, sodda va samimiy gaplash. "
    "MUHIM TALAB: Har qanday xabarga javob berganda albatta turli xil, mos va boy emojilardan (😊, 🚀, ⚡, 🔥, ✨, 💡, 🕌, ⏰, 🤖, 👍 va h.k.) ko'p foydalan! Har bir javobing chiroyli emojilar bilan to'la bo'lsin. "
    "VAQT VA SOAT: Sen O'zbekiston (Farg'ona / Andijon) vaqtini doim aniq bilasan. Har bir xabar boshida senga hozirgi aniq vaqt va sana yuboriladi. Agar foydalanuvchi soat nechi, vaqt qancha, yoki sana haqida so'rasa, shu berilgan aniq vaqtni ayt! Hech qachon 'vaqtni bilmayman' dema! "
    "Savolarga qisqa, aniq va foydali javob ber. "
    "Foydalanuvchi boshqa tilda yozsa, o'sha tilda javob ber. "
    "Agar biror narsani eslatishni so'rasa, 'eslatma saqladim' de. "
    "Agar budilnik so'rasa, vaqtni aniqlashtir. "
    "Doim hurmatli, do'stona va samimiy bo'l. "
    "Bilmasang ochiq ayt, aldama. "
    "Kod so'rasa tayyor ishlatadigan shaklda ber.\n\n"
    + OWNER_PROFILE
)

# Model nusxalarini keshda saqlash
_model_instances: dict[str, genai.GenerativeModel] = {}


def get_model_instance(mode_key: str) -> genai.GenerativeModel:
    """Belgilangan rejimdagi GenerativeModel ni olish"""
    if mode_key not in AVAILABLE_MODELS:
        mode_key = "flash"
    if mode_key not in _model_instances:
        model_id = AVAILABLE_MODELS[mode_key]["id"]
        _model_instances[mode_key] = genai.GenerativeModel(
            model_name=model_id,
            system_instruction=SYSTEM_INSTRUCTION,
        )
    return _model_instances[mode_key]


# Foydalanuvchilarning tanlagan rejimi (default: flash)
user_modes: dict[int, str] = {}

# Har bir foydalanuvchi uchun chat tarixi (user_id -> ChatSession)
user_chats: dict[int, genai.ChatSession] = {}


def get_user_mode(user_id: int) -> str:
    """Foydalanuvchining hozirgi rejimini olish"""
    return user_modes.get(user_id, "flash")


def set_user_mode(user_id: int, mode_key: str) -> bool:
    """Foydalanuvchi rejimini o'zgartirish"""
    if mode_key in AVAILABLE_MODELS:
        user_modes[user_id] = mode_key
        # Model o'zgarganda yangi sessiya ochish
        if user_id in user_chats:
            del user_chats[user_id]
        return True
    return False


def get_chat(user_id: int) -> genai.ChatSession:
    """Foydalanuvchi uchun chat sessiyasini olish yoki yaratish"""
    mode_key = get_user_mode(user_id)
    if user_id not in user_chats:
        model = get_model_instance(mode_key)
        user_chats[user_id] = model.start_chat(history=[])
    return user_chats[user_id]


def _format_time_context() -> str:
    """O'zbekiston bo'yicha aniq hozirgi vaqt va sana matni"""
    now = get_now()
    days = {
        0: "Dushanba", 1: "Seshanba", 2: "Chorshanba",
        3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba"
    }
    day_name = days.get(now.weekday(), "")
    return f"[Hozirgi vaqt: {now.strftime('%H:%M:%S')}, Sana: {now.strftime('%d.%m.%Y')}, {day_name} (O'zbekiston/Farg'ona)]"


async def generate_response(user_id: int, message: str) -> str:
    """Gemini'dan javob olish (avtomatik kvota fallback bilan)"""
    time_ctx = _format_time_context()
    prompt = f"{time_ctx}\nFoydalanuvchi: {message}"

    try:
        chat = get_chat(user_id)
        response = await chat.send_message_async(prompt)
        return response.text
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "Quota" in err_msg or "quota" in err_msg:
            for fallback_id in FALLBACK_MODELS:
                try:
                    fallback_model = genai.GenerativeModel(
                        model_name=fallback_id,
                        system_instruction=SYSTEM_INSTRUCTION,
                    )
                    res = await fallback_model.generate_content_async(prompt)
                    if res.text:
                        return res.text
                except Exception:
                    continue
        return f"❌ Xatolik yuz berdi: {err_msg}"


async def generate_image(prompt: str) -> str | None:
    """Gemini orqali rasm yaratish"""
    try:
        imagen_model = genai.ImageGenerationModel("imagen-3.0-generate-002")
        result = await imagen_model.generate_images_async(
            prompt=prompt,
            number_of_images=1,
        )
        if result.images:
            # Rasmni faylga saqlash
            import os
            os.makedirs("temp", exist_ok=True)
            path = f"temp/image_{hash(prompt) % 100000}.png"
            result.images[0].save(path)
            return path
        return None
    except Exception:
        # Imagen mavjud bo'lmasa, Pollinations API orqali
        return await _generate_image_pollinations(prompt)


async def _generate_image_pollinations(prompt: str) -> str | None:
    """Pollinations.ai orqali bepul rasm yaratish (fallback)"""
    import aiohttp
    import urllib.parse

    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"

    try:
        import os
        os.makedirs("temp", exist_ok=True)
        path = f"temp/image_{hash(prompt) % 100000}.png"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    with open(path, "wb") as f:
                        f.write(await resp.read())
                    return path
        return None
    except Exception:
        return None


async def analyze_with_context(user_id: int, message: str, context: str) -> str:
    """Kontekst bilan javob berish (eslatmalar va hokazo, kvota fallback bilan)"""
    time_ctx = _format_time_context()
    full_message = f"{time_ctx}\n[Foydalanuvchi konteksti: {context}]\n\nFoydalanuvchi: {message}"

    try:
        chat = get_chat(user_id)
        response = await chat.send_message_async(full_message)
        return response.text
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "Quota" in err_msg or "quota" in err_msg:
            for fallback_id in FALLBACK_MODELS:
                try:
                    fallback_model = genai.GenerativeModel(
                        model_name=fallback_id,
                        system_instruction=SYSTEM_INSTRUCTION,
                    )
                    res = await fallback_model.generate_content_async(full_message)
                    if res.text:
                        return res.text
                except Exception:
                    continue
        return f"❌ Xatolik: {err_msg}"
