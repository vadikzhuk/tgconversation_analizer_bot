import os
import logging
import tempfile
import asyncio
from pathlib import Path

from telegram import Update, Message
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from google import genai

# ─────────────────────────────────────────────
# Конфигурация
# ─────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

AUDIO_PROMPT = (
    "Ты — эксперт в области лингвистики, психологии и анализа данных. Твоя задача — проанализировать прикрепленный аудиофайл (или его транскрипцию).\n"
    "ВАЖНО — Метод анализа:\n"
    "Если анализируется АУДИОФАЙЛ: основывай анализ на интонации, паузах, темпе и высоте голоса.\n"
    "Если анализируется ТРАНСКРИПЦИЯ (текст): основывай анализ на выборе слов, структуре предложений и контексте.\n"
    "Пожалуйста, выполни следующие действия:\n"
    "Diarization (Разделение спикеров): Идентифицируй и раздели говорящих, используя нейтральные обозначения: «Спикер 1» и «Спикер 2» и так далее (не упоминай имена, даже если они прозвучат).\n"
    "Эмоциональный анализ: Определи эмоциональное состояние каждого спикера в каждом сегменте.\n"
    "Поиск скрытых смыслов: Выяви сарказм, неуверенность, раздражение, радость или сомнения.\n"
    "Оформи результат в виде точной таблицы со следующими столбцами:\n"
    "Время (примерный интервал, если доступно)\n"
    "Спикер (А или Б)\n"
    "Фрагмент текста (самая значимая фраза)\n"
    "Эмоция (например: Радость, Нейтральность, Фрустрация, Сарказм)\n"
)

SUPPORTED_MIME_TYPES = {
    ".mp3":  "audio/mp3",
    ".wav":  "audio/wav",
    ".ogg":  "audio/ogg",
    ".m4a":  "audio/mp4",
    ".flac": "audio/flac",
    ".aac":  "audio/aac",
    ".opus": "audio/opus",
    ".webm": "audio/webm",
}

# ─────────────────────────────────────────────
# Инициализация
# ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)

# ─────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────
def detect_mime(file_name: str) -> str | None:
    suffix = Path(file_name).suffix.lower()
    return SUPPORTED_MIME_TYPES.get(suffix)


def is_audio_message(message: Message) -> bool:
    return message.voice is not None or message.audio is not None


async def process_audio_with_gemini(audio_path: str, mime_type: str, prompt: str) -> str:
    logger.info("Загружаем файл в Gemini File API: %s (%s)", audio_path, mime_type)

    # Загрузка файла через новый API
    with open(audio_path, "rb") as f:
        audio_file = client.files.upload(
            file=f,
            config={"mime_type": mime_type}
        )

    # Ждём обработки
    while audio_file.state.name == "PROCESSING":
        await asyncio.sleep(2)
        audio_file = client.files.get(name=audio_file.name)

    if audio_file.state.name == "FAILED":
        raise RuntimeError(f"Gemini не смог обработать файл: {audio_file.state.name}")

    # Генерация ответа
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, audio_file]
    )

    client.files.delete(name=audio_file.name)
    return response.text


async def download_audio(message: Message) -> tuple[str, str]:
    """Скачивает аудио из сообщения, возвращает (путь, mime_type)."""
    if message.voice:
        tg_file = await message.voice.get_file()
        file_name = f"voice_{tg_file.file_id}.ogg"
        mime_type = "audio/ogg"
    else:
        tg_file = await message.audio.get_file()
        file_name = message.audio.file_name or f"audio_{tg_file.file_id}.mp3"
        mime_type = detect_mime(file_name) or "audio/mpeg"

    with tempfile.NamedTemporaryFile(suffix=Path(file_name).suffix, delete=False) as tmp:
        tmp_path = tmp.name

    await tg_file.download_to_drive(tmp_path)
    logger.info("Файл сохранён: %s", tmp_path)
    return tmp_path, mime_type


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    bot_username = context.bot.username

    # Проверяем упоминание в тексте или в подписи к файлу
    text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []

    mentioned = any(
        text[e.offset:e.offset + e.length].lower() == f"@{bot_username.lower()}"
        for e in entities if e.type == "mention"
    )

    if not mentioned:
        return

    # Если аудио прямо в этом сообщении
    if is_audio_message(message):
        await _analyze_audio_message(message, message, context)
        return

    # Если reply на аудио
    replied = message.reply_to_message
    if replied and is_audio_message(replied):
        await _analyze_audio_message(replied, message, context)
        return

    await message.reply_text(
        "🎙️ Отправь аудиофайл с упоминанием @" + bot_username + " в подписи, "
        "или сделай reply на аудио с моим упоминанием."
    )


# ─────────────────────────────────────────────
# Обработчики
# ─────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_group = update.message.chat.type in ("group", "supergroup")

    if is_group:
        text = (
            "👋 Привет! Я анализирую аудио беседы.\n\n"
            "🎙️ Как использовать в этом чате:\n"
            "1. Кто-то отправляет голосовое или аудиофайл\n"
            f"2. Сделай <b>reply</b> на это сообщение и напиши <code>@{context.bot.username}</code>\n"
            "3. Я обработаю аудио и отвечу прямо в чат\n\n"
            "В личке можно просто отправить аудио напрямую."
        )
    else:
        text = (
            "👋 Отправь мне голосовое сообщение или аудиофайл — "
            "я попытаюсь транскрибировать и проанализировать его.\n\n"
            "В групповом чате сделай reply на аудио и напиши "
            f"<code>@{context.bot.username}</code>."
        )

    await update.message.reply_text(text, parse_mode="HTML")


async def handle_direct_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Срабатывает в личке: пользователь присылает аудио напрямую.
    """
    if update.message.chat.type != "private":
        return  # в группах работаем только через reply + mention

    await _analyze_audio_message(update.message, update.message, context)


async def _analyze_audio_message(
    audio_msg: Message,
    reply_to: Message,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Общая логика: скачать аудио → Gemini → ответить."""
    await context.bot.send_chat_action(chat_id=reply_to.chat_id, action="typing")
    status_msg = await reply_to.reply_text("⏳ Анализирую аудио…")

    tmp_path = None
    try:
        tmp_path, mime_type = await download_audio(audio_msg)
        response_text = await process_audio_with_gemini(tmp_path, mime_type, AUDIO_PROMPT)

        max_len = 4096
        if len(response_text) <= max_len:
            await status_msg.edit_text(f"🎙️ Анализ аудио:\n\n{response_text}")
        else:
            await status_msg.delete()
            for i in range(0, len(response_text), max_len):
                await reply_to.reply_text(response_text[i : i + max_len])

    except Exception as exc:
        logger.exception("Ошибка при обработке аудио")
        await status_msg.edit_text(f"❌ Ошибка: {exc}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ─────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────
def main() -> None:
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))

    # Личка: аудио напрямую
    app.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_direct_audio))
    app.add_handler(MessageHandler(filters.AUDIO & filters.ChatType.PRIVATE, handle_direct_audio))

    # Группа: любое сообщение (текст, аудио с подписью, reply)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_group_message))

    logger.info("Бот запущен…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
