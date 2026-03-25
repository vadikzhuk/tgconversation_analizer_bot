# 🎙️ Conversation Analyzer Bot

Telegram-бот для анализа аудиодиалогов с помощью Google Gemini AI.

Бот транскрибирует речь, разделяет спикеров (diarization) и выявляет эмоциональный фон каждого участника разговора.

## Возможности

- **Личка** — отправь голосовое сообщение или аудиофайл напрямую
- **Группа** — отправь аудио с упоминанием `@бот` в подписи, или сделай reply на аудио и напиши `@бот`
- Поддерживаемые форматы: mp3, wav, ogg, m4a, flac, aac, opus, webm
- Разделение спикеров по времени
- Эмоциональный анализ каждого фрагмента
- Выявление скрытых смыслов: сарказм, неуверенность, раздражение

## Стек

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v21
- [Google Gemini API](https://ai.google.dev/) (gemini-2.5-flash) через `google-genai`

## Деплой на Railway

### 1. Переменные окружения

В Railway dashboard → Variables добавь:

| Переменная | Описание |
|---|---|
| `TELEGRAM_TOKEN` | Токен бота от @BotFather |
| `GEMINI_API_KEY` | API ключ от [Google AI Studio](https://aistudio.google.com/app/apikey) |

### 2. Настройки бота в @BotFather

```
/setprivacy → Disable        # бот видит все сообщения в группе
/setinline  → включить       # поддержка inline-режима (опционально)
```

### 3. Запуск

Railway автоматически подхватит `Procfile` и запустит бота как worker-процесс.

## Локальный запуск

```bash
git clone https://github.com/ВАШ_РЕПОЗИТОРИЙ
cd ВАШ_РЕПОЗИТОРИЙ
pip install -r requirements.txt

export TELEGRAM_TOKEN="ваш_токен"
export GEMINI_API_KEY="ваш_ключ"

python tg_inline_dialbot.py
```

## Структура проекта

```
├── tg_inline_dialbot.py   # основной код бота
├── requirements.txt
├── Procfile
├── nixpacks.toml
└── README.md
```
