"""
Gemini AI xizmati — chatbot va rasm generatsiya
"""
import re
import google.generativeai as genai
from config import GEMINI_API_KEY, get_now

# Gemini sozlash
genai.configure(api_key=GEMINI_API_KEY)

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

# Foydalanuvchilarning tanlagan rejimi (default: flash)
user_modes: dict[int, str] = {}

# Qisqa suhbat tarixi (user_id -> list of history dicts)
user_histories: dict[int, list[dict]] = {}
MAX_HISTORY_TURNS = 2

# Standart qat'iy tizim yo'riqnomasi — JUDA QISQA VA LO'NDA JAVOBLAR
GENERAL_SYSTEM_INSTRUCTION = (
    "Sen aqlli, chaqqon va odobli shaxsiy Telegram AI yordamchisisan. "
    "O'zbek tilida gaplash. "
    "ENG ASOSIY TALAB — JAVOBLAR JUDA QISQA VA LO'NDA BO'LSIN: "
    "1. Foydalanuvchi uzun matnlarni o'qishni aslo yoqtirmaydi ('o'qish zerikarli'). "
    "Javobing 1 yoki uzog'i bilan 2 qisqa gapdan oshmasin! "
    "2. Foydalanuvchi nima so'rasa, FAQAT o'sha savolga to'g'ri va qisqa javob ber. "
    "3. Hech qachon o'zingdan ortiqcha mavzularni (kod yozamizmi, sxema chizamizmi, fizika yechamizmi, vaqtni bilasizmi) tiqishtirma yoki taklif qilma! "
    "4. 'salom', 'alyo', 'nima gap', 'qale' kabi so'zlarga bor-yo'g'i 1 qisqa samimiy gap bilan javob ber "
    "(masalan: 'Tinchlik, alhamdulillah! Qanday yordam kerak? 😊' yoki 'Eshityapman, aloqadaman! 😊'). "
    "5. Hech qachon ro'yxatlar tuzma, faqat foydalanuvchi 'batafsil ro'yxat ber' deb so'rasagina yoz. "
    "6. 1-2 ta mos emoji ishlat."
)

# Shaxsiy profil (Faqat xabar aynan 'asa' so'zi bilan boshlanganda ishlatiladi)
OWNER_PROFILE_INSTRUCTION = (
    "Foydalanuvchi sening egang — Sanjarbek Xabibullayev (Sanjik). "
    "2007-yilda tug'ilgan, Andijonlik, 2-kurs talaba. "
    "Andijoncha samimiy, do'stona gaplash, lekin BARIBIR JUDA QISQA (1-2 gap) javob ber! "
    "O'zingdan hech qachon mavzular tiqishtirma, faqat Sanjarbek o'zi so'raganiga lo'nda javob qaytar."
)


def get_user_mode(user_id: int) -> str:
    """Foydalanuvchining hozirgi rejimini olish"""
    return user_modes.get(user_id, "flash")


def set_user_mode(user_id: int, mode_key: str) -> bool:
    """Foydalanuvchi rejimini o'zgartirish"""
    if mode_key in AVAILABLE_MODELS:
        user_modes[user_id] = mode_key
        if user_id in user_histories:
            del user_histories[user_id]
        return True
    return False


def _build_model(mode_key: str, is_owner: bool) -> genai.GenerativeModel:
    """Model instansiyasini yaratish"""
    if mode_key not in AVAILABLE_MODELS:
        mode_key = "flash"
    model_id = AVAILABLE_MODELS[mode_key]["id"]
    sys_instruction = (
        f"{GENERAL_SYSTEM_INSTRUCTION}\n\n{OWNER_PROFILE_INSTRUCTION}"
        if is_owner
        else GENERAL_SYSTEM_INSTRUCTION
    )
    return genai.GenerativeModel(
        model_name=model_id,
        system_instruction=sys_instruction,
    )


async def generate_response(user_id: int, message: str) -> str:
    """Gemini'dan qisqa va lo'nda javob olish"""
    msg_clean = message.strip()

    # Maxfiylik qoidasi: 'asa' bilan boshlanganini tekshirish
    is_owner = False
    if msg_clean.lower().startswith("asa"):
        is_owner = True
        msg_clean = re.sub(r"^asa[\s,.:!?-]*", "", msg_clean, flags=re.IGNORECASE).strip()
        if not msg_clean:
            return "Eshityapman Sanjik, tinchlikmi? Qanday yordam beray? 😊"

    mode_key = get_user_mode(user_id)
    model = _build_model(mode_key, is_owner)

    history = user_histories.get(user_id, [])
    recent_history = history[-MAX_HISTORY_TURNS * 2 :]

    try:
        chat = model.start_chat(history=recent_history)
        response = await chat.send_message_async(msg_clean)
        ans = response.text.strip()

        recent_history.append({"role": "user", "parts": [msg_clean]})
        recent_history.append({"role": "model", "parts": [ans]})
        user_histories[user_id] = recent_history[-MAX_HISTORY_TURNS * 2 :]

        return ans
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "Quota" in err_msg or "quota" in err_msg:
            for fallback_id in FALLBACK_MODELS:
                try:
                    fallback_model = genai.GenerativeModel(
                        model_name=fallback_id,
                        system_instruction=GENERAL_SYSTEM_INSTRUCTION,
                    )
                    res = await fallback_model.generate_content_async(msg_clean)
                    if res.text:
                        return res.text.strip()
                except Exception:
                    continue
        return f"❌ Xatolik yuz berdi: {err_msg}"


async def analyze_with_context(user_id: int, message: str, context: str) -> str:
    """Eslatmalar konteksti bilan javob berish"""
    prompt = f"[Eslatma konteksti: {context}]\n{message}"
    return await generate_response(user_id, prompt)


async def generate_image(prompt: str) -> str | None:
    """Gemini orqali rasm yaratish"""
    try:
        imagen_model = genai.ImageGenerationModel("imagen-3.0-generate-002")
        result = await imagen_model.generate_images_async(
            prompt=prompt,
            number_of_images=1,
        )
        if result.images:
            import os
            os.makedirs("temp", exist_ok=True)
            path = f"temp/image_{hash(prompt) % 100000}.png"
            result.images[0].save(path)
            return path
        return None
    except Exception:
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
