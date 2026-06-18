"""
bot/handlers.py — обработчики Telegram-бота (Gemini-версия)
"""
import logging
import sys
import os

# Добавляем корень проекта в путь, чтобы найти gemini_assistant.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telegram import Update
from telegram.ext import ContextTypes

from .keyboards import (
    main_menu, back_to_main_button, settings_menu,
    feedback_menu, rating_keyboard
)
from .state_manager import StateManager
from .rate_limiter import rate_limiter
from .admin_handlers import AdminHandlers

logger = logging.getLogger(__name__)

# ─── Флаг совместимости (нужен bot.py при старте) ────────────────────────────
ENHANCED_NEURALEX_AVAILABLE = False

# ─── Инициализация GeminiAssistant ──────────────────────────────────────────
law_assistant = None

def check_openai_availability() -> bool:
    """Проверяет наличие Gemini API key."""
    try:
        from .config import GEMINI_API_KEY
        return bool(GEMINI_API_KEY)
    except Exception as e:
        logging.error(f'GEMINI_API_KEY отсутствует: {e}')
        return False

try:
    from .config import GEMINI_API_KEY, GEMINI_MODEL, REDIS_URL

    # Пробуем подключить ChromaDB (RAG по базе законов) — необязательно
    vector_store = None
    try:
        from langchain_community.vectorstores import Chroma
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from .config import CHROMA_DB_PATH
        embeddings = HuggingFaceEmbeddings(
            model_name='sentence-transformers/paraphrase-multilingual-mpnet-base-v2'
        )
        vector_store = Chroma(
            persist_directory=CHROMA_DB_PATH,
            embedding_function=embeddings,
            collection_name='legal_documents'
        )
        logger.info('✅ ChromaDB подключён (RAG активен)')
    except Exception as e:
        logger.warning(f'⚠️ ChromaDB недоступен, работаем без RAG: {e}')

    from gemini_assistant import GeminiAssistant
    law_assistant = GeminiAssistant(
        api_key=GEMINI_API_KEY,
        model=GEMINI_MODEL,
        vector_store=vector_store,
        redis_url=REDIS_URL,
    )
    logger.info('✅ GeminiAssistant инициализирован')

except Exception as e:
    logger.error(f'❌ Ошибка инициализации GeminiAssistant: {e}')
    law_assistant = None

# ─── Вспомогательные объекты ─────────────────────────────────────────────────
state_manager = StateManager()
admin_handlers = AdminHandlers()


# ─── /start ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start и /admin"""
    user = update.effective_user
    user_id = str(user.id)

    # Проверяем, это /admin?
    if update.message and update.message.text and update.message.text.startswith('/admin'):
        if admin_handlers.admin_panel.is_admin(user_id):
            await update.message.reply_text(
                "🔧 **АДМИН-ПАНЕЛЬ**\n\nВыберите раздел:",
                parse_mode='Markdown',
                reply_markup=admin_handlers.admin_panel.get_admin_menu()
            )
            return
        else:
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return

    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я — бот @LegalHelpRU_bot, помощник по юридическим вопросам "
        "на основе российского законодательства.\n\n"
        "⚠️ Важно: Я бот, не дипломированный юрист. Мои ответы носят "
        "информационный характер и не являются официальной юридической консультацией.\n\n"
        "❓ Задайте вопрос текстом или выберите действие в меню:"
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=main_menu()
    )
    state_manager.clear_user_state(user_id)


# ─── Обработчик кнопок ───────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все нажатия inline-кнопок"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    data = query.data

    # Админ-колбэки
    if data.startswith('admin_'):
        await admin_handlers.handle_admin_callback(query, user_id)
        return

    # ── Главное меню ──────────────────────────────────────────────────────────
    if data == 'back_to_main':
        state_manager.clear_user_state(user_id)
        await query.edit_message_text(
            "🏠 Главное меню\n\nВыберите действие:",
            reply_markup=main_menu()
        )

    elif data == 'ask':
        state_manager.set_user_state(user_id, 'asking_question')
        await query.edit_message_text(
            "❓ *Задайте ваш вопрос*\n\n"
            "Напишите юридический вопрос, и я постараюсь помочь.\n\n"
            "_Пример: «Как правильно уволить сотрудника по статье?»_",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )

    elif data == 'check_document':
        state_manager.set_user_state(user_id, 'waiting_document')
        await query.edit_message_text(
            "📄 *Проверка документа*\n\n"
            "Отправьте файл документа (PDF, DOCX, TXT) или изображение, "
            "и я проверю его на соответствие российскому законодательству.\n\n"
            "⚠️ Максимальный размер файла: 20 МБ",
            parse_mode='Markdown',
            reply_markup=back_to_main_button()
        )

    elif data == 'feedback':
        await query.edit_message_text(
            "💬 *Обратная связь*\n\nВыберите тип обратной связи:",
            parse_mode='Markdown',
            reply_markup=feedback_menu()
        )

    elif data == 'settings':
        await query.edit_message_text(
            "⚙️ *Настройки*\n\nВыберите раздел:",
            parse_mode='Markdown',
            reply_markup=settings_menu()
        )

    elif data == 'clear_history':
        if law_assistant:
            law_assistant.clear_history(user_id)
        state_manager.clear_user_state(user_id)
        await query.edit_message_text(
            "✅ История диалога очищена!\n\nМожете начать новый разговор.",
            reply_markup=main_menu()
        )

    # ── Оценки ───────────────────────────────────────────────────────────────
    elif data == 'rate_answer':
        await query.edit_message_text(
            "⭐ Оцените последний ответ:",
            reply_markup=rating_keyboard()
        )

    elif data.startswith('rate_'):
        rating_map = {
            'rate_1': 1, 'rate_2': 2, 'rate_3': 3,
            'rate_4': 4, 'rate_5': 5,
            'rate_helpful': 5, 'rate_not_helpful': 1
        }
        rating = rating_map.get(data, 3)
        if law_assistant:
            law_assistant.rate_last_answer(user_id, rating)
        await query.edit_message_text(
            f"✅ Спасибо за оценку! ({rating}/5)\n\nВаш отзыв поможет улучшить бота.",
            reply_markup=main_menu()
        )

    # ── Настройки / обратная связь (заглушки) ────────────────────────────────
    elif data in ('settings_notifications', 'settings_stats', 'settings_language',
                  'my_consultations', 'export_history'):
        await query.edit_message_text(
            "🚧 Эта функция находится в разработке.\n\nСкоро будет доступна!",
            reply_markup=back_to_main_button()
        )

    elif data in ('report_bug', 'suggest_improvement'):
        state_manager.set_user_state(user_id, 'sending_feedback')
        await query.edit_message_text(
            "✍️ Напишите ваш отзыв или сообщение об ошибке — я передам его разработчикам.",
            reply_markup=back_to_main_button()
        )

    else:
        await query.edit_message_text(
            "❓ Неизвестная команда. Вернитесь в главное меню.",
            reply_markup=main_menu()
        )


# ─── Текстовые сообщения ─────────────────────────────────────────────────────
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения пользователей"""
    user = update.effective_user
    user_id = str(user.id)
    text = update.message.text.strip()

    # Проверка rate limit
    if not rate_limiter.is_allowed(user_id):
        remaining = rate_limiter.get_reset_time(user_id)
        wait_seconds = int(remaining) if remaining else 60
        await update.message.reply_text(
            f"⏳ Слишком много запросов. Подождите {wait_seconds} секунд.",
            reply_markup=back_to_main_button()
        )
        return

    if not law_assistant:
        await update.message.reply_text(
            "❌ ИИ-ассистент временно недоступен. Попробуйте позже.",
            reply_markup=main_menu()
        )
        return

    user_state = state_manager.get_user_state(user_id)

    # Обратная связь
    if user_state == 'sending_feedback':
        state_manager.clear_user_state(user_id)
        await update.message.reply_text(
            "✅ Спасибо! Ваше сообщение получено.",
            reply_markup=main_menu()
        )
        return

    # Отправляем индикатор ввода
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='typing'
    )

    try:
        answer, _ = law_assistant.conversational(text, user_id)
        state_manager.save_last_answer(user_id, text, answer)

        # Разбиваем длинные ответы (лимит Telegram — 4096 символов)
        if len(answer) > 4000:
            for i in range(0, len(answer), 4000):
                chunk = answer[i:i+4000]
                if i + 4000 >= len(answer):
                    await update.message.reply_text(chunk, reply_markup=back_to_main_button())
                else:
                    await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(answer, reply_markup=back_to_main_button())

    except Exception as e:
        logger.error(f"Ошибка Gemini API для {user_id}: {e}")
        err = str(e).lower()
        if 'quota' in err or 'limit' in err or '429' in err:
            msg = (
                "⚠️ Превышен лимит запросов к Gemini API.\n\n"
                "Попробуйте через несколько минут или получите новый ключ: "
                "https://aistudio.google.com/apikey"
            )
        elif 'api_key' in err or 'invalid' in err:
            msg = "❌ Ошибка ключа Gemini API. Проверьте GEMINI_API_KEY в .env"
        else:
            msg = f"❌ Произошла ошибка при обработке запроса.\n\nПопробуйте позже."
        await update.message.reply_text(msg, reply_markup=main_menu())


# ─── Документы и файлы ───────────────────────────────────────────────────────
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает файлы: PDF, DOCX, изображения"""
    user = update.effective_user
    user_id = str(user.id)

    if not rate_limiter.is_allowed(user_id):
        await update.message.reply_text(
            "⏳ Слишком много запросов. Подождите немного.",
            reply_markup=back_to_main_button()
        )
        return

    if not law_assistant:
        await update.message.reply_text(
            "❌ ИИ-ассистент временно недоступен.",
            reply_markup=main_menu()
        )
        return

    # Определяем тип вложения
    mime_type = None
    file_obj = None

    if update.message.document:
        doc = update.message.document
        mime_type = doc.mime_type
        file_size = doc.file_size

        # Карта допустимых MIME-типов
        allowed_mimes = {
            'application/pdf': '.pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/msword': '.doc',
            'text/plain': '.txt',
            'image/jpeg': '.jpg',
            'image/png': '.png',
        }

        if mime_type not in allowed_mimes:
            await update.message.reply_text(
                "❌ Неподдерживаемый тип файла.\n\n"
                "Поддерживаются: PDF, DOCX, DOC, TXT, JPG, PNG",
                reply_markup=back_to_main_button()
            )
            return

        if file_size > 20 * 1024 * 1024:
            await update.message.reply_text(
                "❌ Файл слишком большой (максимум 20 МБ).",
                reply_markup=back_to_main_button()
            )
            return

        file_obj = await doc.get_file()

    elif update.message.photo:
        # Берём фото максимального размера
        photo = update.message.photo[-1]
        mime_type = 'image/jpeg'
        file_obj = await photo.get_file()

    else:
        await update.message.reply_text(
            "❌ Не удалось обработать вложение.",
            reply_markup=back_to_main_button()
        )
        return

    # Скачиваем файл
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='typing'
    )

    processing_msg = await update.message.reply_text(
        "⏳ Анализирую документ, подождите..."
    )

    try:
        file_bytes = await file_obj.download_as_bytearray()
        file_bytes = bytes(file_bytes)

        # Получаем подсказку пользователя (caption) если есть
        user_query = update.message.caption or ""

        answer, _ = law_assistant.conversational(
            query=user_query,
            session_id=user_id,
            file_bytes=file_bytes,
            file_mime=mime_type
        )

        await processing_msg.delete()

        if len(answer) > 4000:
            for i in range(0, len(answer), 4000):
                chunk = answer[i:i+4000]
                if i + 4000 >= len(answer):
                    await update.message.reply_text(chunk, reply_markup=back_to_main_button())
                else:
                    await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(answer, reply_markup=back_to_main_button())

    except Exception as e:
        logger.error(f"Ошибка при обработке документа для {user_id}: {e}")
        await processing_msg.delete()
        await update.message.reply_text(
            "❌ Ошибка при анализе документа. Попробуйте позже.",
            reply_markup=main_menu()
        )
