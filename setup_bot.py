#!/usr/bin/env python3
"""
Скрипт для проверки настройки бота перед запуском
"""

import os
import sys
from dotenv import load_dotenv

def check_environment():
    """Проверяет наличие всех необходимых переменных окружения"""
    load_dotenv()
    
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'OPENAI_API_KEY'
    ]
    
    optional_vars = [
        'REDIS_URL'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Отсутствуют следующие переменные окружения:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nОтредактируйте файл .env и добавьте реальные значения")
        return False
    
    print("✅ Все переменные окружения настроены")
    
    # Проверяем опциональные переменные
    for var in optional_vars:
        if os.getenv(var):
            print(f"✅ {var} настроен")
        else:
            print(f"⚠️  {var} не настроен (будет использовано значение по умолчанию)")
    
    return True

def check_chroma_db():
    """Проверяет наличие базы данных Chroma"""
    db_path = "chroma_db_legal_bot_part1"
    if os.path.exists(db_path):
        # Проверяем, что в директории есть файлы
        if os.listdir(db_path):
            print("✅ База данных Chroma найдена и содержит данные")
        else:
            print("⚠️  База данных Chroma найдена, но пуста")
        return True
    else:
        print("❌ База данных Chroma не найдена")
        print(f"   Ожидается в: {db_path}")
        print("   Убедитесь, что векторная база данных создана")
        return False

def check_imports():
    """Проверяет возможность импорта всех необходимых модулей"""
    try:
        import telegram
        print("✅ python-telegram-bot установлен")
    except ImportError:
        print("❌ python-telegram-bot не установлен")
        return False
    
    try:
        import langchain
        print("✅ langchain установлен")
    except ImportError:
        print("❌ langchain не установлен")
        return False
    
    try:
        import openai
        print("✅ openai установлен")
    except ImportError:
        print("❌ openai не установлен")
        return False
    
    try:
        import redis
        print("✅ redis установлен")
    except ImportError:
        print("❌ redis не установлен")
        return False
    
    try:
        import chromadb
        print("✅ chromadb установлен")
    except ImportError:
        print("❌ chromadb не установлен")
        return False
    
    return True

def check_redis_connection():
    """Проверяет подключение к Redis"""
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        client = redis.Redis.from_url(redis_url)
        client.ping()
        print("✅ Подключение к Redis успешно")
        return True
    except Exception as e:
        print(f"⚠️  Не удалось подключиться к Redis: {e}")
        print("   Бот будет работать без кэширования")
        return True  # Не критично для работы бота

def check_bot_structure():
    """Проверяет структуру файлов бота"""
    required_files = [
        'bot/bot.py',
        'bot/handlers.py',
        'bot/keyboards.py',
        'bot/config.py',
        'neuralex-main/neuralex_main.py',
        'neuralex-main/cache.py',
        'neuralex-main/chains.py',
        'neuralex-main/prompts.py',
        'run_bot.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Отсутствуют следующие файлы:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    
    print("✅ Все необходимые файлы найдены")
    return True

def main():
    print("🔍 Проверка настройки телеграм-бота neuralex...\n")
    
    checks = [
        check_bot_structure(),
        check_imports(),
        check_environment(),
        check_chroma_db(),
        check_redis_connection()
    ]
    
    if all(checks):
        print("\n✅ Все проверки пройдены! Бот готов к запуску.")
        print("Запустите бота командой: python run_bot.py")
        print("\n📝 Не забудьте:")
        print("   - Запустить Redis сервер (если используете кэширование)")
        print("   - Проверить токен бота в @BotFather")
        print("   - Убедиться, что векторная база данных содержит данные")
    else:
        print("\n❌ Обнаружены проблемы. Исправьте их перед запуском бота.")
        sys.exit(1)

if __name__ == "__main__":
    main()