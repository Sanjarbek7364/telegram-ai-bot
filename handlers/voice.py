"""
Ovozli xabar handler — voice → matn
"""
import os
import tempfile
import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.gemini_service import generate_response
from services.memory_service import ensure_user

logger = logging.getLogger(__name__)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ovozli xabarni matnga o'girish"""
    user = update.effective_user
    await ensure_user(user.id, user.first_name or "")

    await update.message.reply_text("🎤 Ovozli xabar qayta ishlanmoqda...")
    await update.message.chat.send_action("typing")

    try:
        # Ovozli faylni yuklab olish
        voice = update.message.voice or update.message.audio
        if not voice:
            await update.message.reply_text("❌ Ovozli xabar topilmadi.")
            return

        file = await context.bot.get_file(voice.file_id)

        # Temp faylga saqlash
        os.makedirs("temp", exist_ok=True)
        ogg_path = os.path.join("temp", f"voice_{user.id}_{voice.file_unique_id}.ogg")
        wav_path = os.path.join("temp", f"voice_{user.id}_{voice.file_unique_id}.wav")

        await file.download_to_drive(ogg_path)

        # OGG → WAV konvertatsiya (pydub + ffmpeg)
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_ogg(ogg_path)
            audio.export(wav_path, format="wav")
        except Exception as e:
            logger.error(f"Audio konvertatsiya xatolik: {e}")
            # pydub/ffmpeg bo'lmasa, Gemini'ga to'g'ridan-to'g'ri yuborish
            text = await _transcribe_with_gemini(ogg_path)
            if text:
                await _send_transcription(update, context, user.id, text)
            else:
                await update.message.reply_text(
                    "❌ Ovozni matnga o'girib bo'lmadi.\n"
                    "💡 `ffmpeg` o'rnating: https://ffmpeg.org/download.html"
                )
            return
        finally:
            _safe_remove(ogg_path)

        # WAV → Matn (SpeechRecognition)
        text = await _transcribe_speech(wav_path)
        _safe_remove(wav_path)

        if text:
            await _send_transcription(update, context, user.id, text)
        else:
            await update.message.reply_text("❌ Ovozni aniqlab bo'lmadi. Qaytadan urinib ko'ring.")

    except Exception as e:
        logger.error(f"Voice handler xatolik: {e}")
        await update.message.reply_text(f"❌ Xatolik yuz berdi: {str(e)}")


async def _transcribe_speech(wav_path: str) -> str | None:
    """SpeechRecognition bilan matnga o'girish"""
    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        # Google Speech Recognition (bepul)
        text = recognizer.recognize_google(audio_data, language="uz-UZ")
        return text
    except ImportError:
        logger.warning("SpeechRecognition kutubxonasi yo'q")
        return None
    except Exception as e:
        logger.error(f"Speech recognition xatolik: {e}")
        # O'zbek tili tanilmasa, ruscha urinish
        try:
            text = recognizer.recognize_google(audio_data, language="ru-RU")
            return text
        except Exception:
            return None


async def _transcribe_with_gemini(audio_path: str) -> str | None:
    """Gemini bilan audio transkripsiya (fallback)"""
    try:
        import google.generativeai as genai

        model = genai.GenerativeModel("gemini-3.8-flash")
        audio_file = genai.upload_file(audio_path)
        response = model.generate_content(
            [
                "Bu ovozli xabardagi gapni aniq matnga yoz. "
                "Faqat aytilgan so'zlarni yoz, boshqa hech narsa qo'shma.",
                audio_file,
            ]
        )
        return response.text.strip() if response.text else None
    except Exception as e:
        logger.error(f"Gemini transkripsiya xatolik: {e}")
        return None


async def _send_transcription(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str
):
    """Transkripsiya natijasini yuborish va AI javob berish"""
    await update.message.reply_text(
        f"📝 **Ovozli xabar matni:**\n\n{text}",
        parse_mode="Markdown",
    )

    # AI javob ham berish
    await update.message.chat.send_action("typing")
    response = await generate_response(user_id, text)
    await update.message.reply_text(f"🤖 {response}")


def _safe_remove(path: str):
    """Faylni xavfsiz o'chirish"""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
