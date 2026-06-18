#!/usr/bin/env python3
"""
apply_gemini_patch.py — автоматически переключает бота с OpenAI на Gemini.
Запускай из корня проекта: python apply_gemini_patch.py
"""
import re, shutil
from pathlib import Path

HANDLERS = Path("bot/handlers.py")
CONFIG   = Path("bot/config.py")

def patch_handlers():
    if not HANDLERS.exists():
        print("❌ bot/handlers.py не найден. Запускай из корня проекта.")
        return False

    shutil.copy(HANDLERS, HANDLERS.with_suffix(".py.bak"))
    print("✅ Бэкап: bot/handlers.py.bak")

    code = HANDLERS.read_text(encoding="utf-8")

    # ── Патч 1: Замена импортов neuralex на GeminiAssistant ───────────────────
    old_neuralex = re.compile(
        r"# Пытаемся импортировать расширенную версию.*?ENHANCED_NEURALEX_AVAILABLE = False\n",
        re.DOTALL
    )
    new_import = (
        "import sys as _sys, os as _os\n"
        "_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))\n"
        "from gemini_assistant import GeminiAssistant\n"
        "ENHANCED_NEURALEX_AVAILABLE = False\n"
    )
    if old_neuralex.search(code):
        code = old_neuralex.sub(new_import, code)
        print("✅ Патч 1: импорты → GeminiAssistant")
    else:
        print("⚠️  Патч 1: блок neuralex не найден (возможно уже пропатчено)")

    # ── Патч 2: check_openai_availability → check_gemini_availability ─────────
    old_check = re.compile(
        r"def check_openai_availability\(\).*?(?=\ndef |\nclass |\Z)",
        re.DOTALL
    )
    new_check = (
        "def check_openai_availability() -> bool:\n"
        "    \"\"\"Проверяет наличие Gemini API key.\"\"\"\n"
        "    try:\n"
        "        from .config import GEMINI_API_KEY\n"
        "        return bool(GEMINI_API_KEY)\n"
        "    except Exception as e:\n"
        "        logging.error(f'GEMINI_API_KEY отсутствует: {e}')\n"
        "        return False\n\n"
    )
    if old_check.search(code):
        code = old_check.sub(new_check, code)
        print("✅ Патч 2: check_openai_availability → Gemini")
    else:
        print("⚠️  Патч 2: функция не найдена")

    # ── Патч 3: Инициализация law_assistant ───────────────────────────────────
    # Ищем блок от "from langchain_openai" до создания law_assistant
    old_init = re.compile(
        r"from langchain_openai import ChatOpenAI.*?law_assistant = (?:neuralex|EnhancedNeuralex)\(.*?\)\n",
        re.DOTALL
    )
    new_init = (
        "        from .config import GEMINI_API_KEY, GEMINI_MODEL, REDIS_URL\n\n"
        "        # Опционально: RAG через ChromaDB (если нужен поиск по законам)\n"
        "        vector_store = None\n"
        "        try:\n"
        "            from langchain_community.vectorstores import Chroma\n"
        "            from langchain_community.embeddings import HuggingFaceEmbeddings\n"
        "            embeddings = HuggingFaceEmbeddings(\n"
        "                model_name='sentence-transformers/paraphrase-multilingual-mpnet-base-v2'\n"
        "            )\n"
        "            vector_store = Chroma(\n"
        "                persist_directory=CHROMA_DB_PATH,\n"
        "                embedding_function=embeddings,\n"
        "                collection_name='legal_documents'\n"
        "            )\n"
        "            logger.info('✅ ChromaDB подключён')\n"
        "        except Exception as e:\n"
        "            logger.warning(f'⚠️ ChromaDB недоступен, без RAG: {e}')\n\n"
        "        law_assistant = GeminiAssistant(\n"
        "            api_key=GEMINI_API_KEY,\n"
        "            model=GEMINI_MODEL,\n"
        "            vector_store=vector_store,\n"
        "            redis_url=REDIS_URL,\n"
        "        )\n"
        "        logger.info('✅ GeminiAssistant инициализирован')\n"
    )
    if old_init.search(code):
        code = old_init.sub(new_init, code)
        print("✅ Патч 3: инициализация → GeminiAssistant")
    else:
        print("⚠️  Патч 3: блок инициализации не найден — замени вручную")

    # ── Патч 4: Тексты ошибок ────────────────────────────────────────────────
    replacements = [
        ("https://platform.openai.com/account/billing", "https://aistudio.google.com/apikey"),
        ("OpenAI API", "Gemini API"),
        ("openai_error", "api_error"),
        ("GPT", "Gemini"),
    ]
    for old, new in replacements:
        code = code.replace(old, new)
    print("✅ Патч 4: тексты ошибок → Gemini")

    HANDLERS.write_text(code, encoding="utf-8")
    print("\n🎉 handlers.py обновлён!")
    return True


def patch_config():
    if not CONFIG.exists():
        print("⚠️  bot/config.py не найден, пропускаю")
        return
    shutil.copy(CONFIG, CONFIG.with_suffix(".py.bak"))
    import shutil as sh
    sh.copy("config_gemini.py", str(CONFIG))
    print("✅ bot/config.py заменён на config_gemini.py")


if __name__ == "__main__":
    print("🔧 Применяю патч Gemini...\n")
    ok = patch_handlers()
    if ok:
        patch_config()

    print("\n" + "="*50)
    print("📋 СЛЕДУЮЩИЕ ШАГИ:")
    print("="*50)
    print("1. Скопируй gemini_assistant.py в корень проекта")
    print("2. Получи бесплатный API ключ: https://aistudio.google.com/apikey")
    print("3. Создай .env из .env.gemini.example и заполни GEMINI_API_KEY")
    print("4. pip install google-generativeai")
    print("5. python run_bot.py")
    print()
    print("⚠️  ВАЖНО: Перевыпусти токен Telegram бота у @BotFather!")
    print("   Команда: /revoke → выбери бота → получи новый токен")
