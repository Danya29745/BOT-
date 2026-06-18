import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ─── Telegram ────────────────────────────────────────────────────────────────
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env")

# ─── Google Gemini AI ────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY не найден в .env\n"
        "Получить бесплатно: https://aistudio.google.com/apikey"
    )

# Заглушки для обратной совместимости с handlers.py
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

# ─── Redis ───────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# ─── Прочее ──────────────────────────────────────────────────────────────────
LOGO_PATH = os.getenv('LOGO_PATH')
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 МБ
ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.jpg', '.jpeg', '.png']
CHROMA_DB_PATH = "chroma_db_legal_bot_part1"
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '7965055989')
ENABLE_ADMIN_NOTIFICATIONS = os.getenv('ENABLE_ADMIN_NOTIFICATIONS', 'true').lower() == 'true'

logging.info(f"✅ Конфигурация загружена | модель: {GEMINI_MODEL}")
