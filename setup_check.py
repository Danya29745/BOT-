#!/usr/bin/env python3
"""
Расширенная проверка настройки бота с диагностикой
"""

import os
import sys
from dotenv import load_dotenv

def check_environment():
    """Проверяет переменные окружения"""
    print("🔍 Проверка переменных окружения...")
    
    load_dotenv()
    
    required_vars = {
        'TELEGRAM_BOT_TOKEN': 'Токен Telegram бота (получить у @BotFather)',
        'OPENAI_API_KEY': 'API ключ OpenAI (получить на platform.openai.com)'
    }
    
    optional_vars = {
        'REDIS_URL': 'URL Redis сервера (по умолчанию: redis://localhost:6379/0)',
        'LOG_LEVEL': 'Уровень логирования (по умолчанию: INFO)'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            missing_vars.append((var, description))
        elif value == f"your_{var.lower()}_here":
            missing_vars.append((var, f"{description} (найден placeholder)"))
        else:
            print(f"✅ {var}: настроен")
    
    if missing_vars:
        print("\n❌ Отсутствуют или неправильно настроены переменные:")
        for var, description in missing_vars:
            print(f"   - {var}: {description}")
        print(f"\nДобавьте их в файл .env в корне проекта")
        return False
    
    # Проверяем опциональные переменные
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"⚠️  {var}: не настроен ({description})")
    
    return True

def check_imports():
    """Проверяет импорты"""
    print("\n🔍 Проверка зависимостей...")
    
    required_packages = [
        ('telegram', 'python-telegram-bot'),
        ('langchain', 'langchain'),
        ('langchain_openai', 'langchain-openai'),
        ('openai', 'openai'),
        ('redis', 'redis'),
        ('chromadb', 'chromadb'),
        ('fitz', 'PyMuPDF'),
        ('docx', 'python-docx'),
        ('dotenv', 'python-dotenv')
    ]
    
    missing_packages = []
    for package, pip_name in required_packages:
        try:
            __import__(package)
            print(f"✅ {pip_name}: установлен")
        except ImportError:
            missing_packages.append(pip_name)
            print(f"❌ {pip_name}: не установлен")
    
    if missing_packages:
        print(f"\nУстановите недостающие пакеты:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_files():
    """Проверяет наличие файлов"""
    print("\n🔍 Проверка файлов...")
    
    required_files = [
        '.env',
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
        if os.path.exists(file_path):
            print(f"✅ {file_path}: найден")
        else:
            missing_files.append(file_path)
            print(f"❌ {file_path}: отсутствует")
    
    if missing_files:
        if '.env' in missing_files:
            print("\n💡 Файл .env отсутствует!")
            print("Создайте файл .env и добавьте ваши токены:")
            print("TELEGRAM_BOT_TOKEN=ваш_токен")
            print("OPENAI_API_KEY=ваш_ключ")
        return False
    
    return True

def check_chroma_db():
    """Проверяет базу данных Chroma"""
    print("\n🔍 Проверка базы данных Chroma...")
    
    db_path = "chroma_db_legal_bot_part1"
    if os.path.exists(db_path):
        if os.listdir(db_path):
            print(f"✅ База данных Chroma: найдена и содержит данные")
            return True
        else:
            print(f"⚠️  База данных Chroma: найдена, но пуста")
            return True
    else:
        print(f"❌ База данных Chroma: не найдена в {db_path}")
        return False

def check_redis():
    """Проверяет подключение к Redis"""
    print("\n🔍 Проверка Redis...")
    
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        client = redis.Redis.from_url(redis_url)
        client.ping()
        print(f"✅ Redis: подключение успешно ({redis_url})")
        return True
    except Exception as e:
        print(f"⚠️  Redis: недоступен ({e})")
        print("   Бот будет работать без кэширования")
        return True  # Не критично

def test_bot_initialization():
    """Тестирует инициализацию бота"""
    print("\n🔍 Тестирование инициализации бота...")
    
    try:
        # Тестируем импорт конфигурации
        from bot.config import TOKEN, OPENAI_API_KEY
        print("✅ Конфигурация: загружена успешно")
        
        # Тестируем подключение к OpenAI
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        try:
            models = openai_client.models.list()
            print("✅ OpenAI API: подключение успешно")
        except Exception as e:
            print(f"❌ OpenAI API: ошибка подключения ({e})")
            return False
        
        # Тестируем импорт основных модулей
        from bot.handlers import start, button_handler
        print("✅ Обработчики: импортированы успешно")
        
        from neuralex_main import neuralex
        print("✅ Neuralex: импортирован успешно")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        return False

def main():
    print("🤖 Диагностика телеграм-бота Neuralex\n")
    
    checks = [
        check_files(),
        check_imports(),
        check_environment(),
        check_chroma_db(),
        check_redis(),
        test_bot_initialization()
    ]
    
    if all(checks):
        print("\n🎉 Все проверки пройдены! Бот готов к запуску.")
        print("\nЗапустите бота командой:")
        print("python run_bot.py")
        
        print("\n📋 Чек-лист перед запуском:")
        print("1. ✅ Все зависимости установлены")
        print("2. ✅ Переменные окружения настроены")
        print("3. ✅ База данных Chroma доступна")
        print("4. ✅ Файлы бота на месте")
        print("5. ⚠️  Запустите Redis сервер (опционально)")
        
    else:
        print("\n❌ Обнаружены проблемы. Исправьте их перед запуском.")
        sys.exit(1)

if __name__ == "__main__":
    main()