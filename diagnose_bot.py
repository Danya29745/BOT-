#!/usr/bin/env python3
"""
Скрипт диагностики проблем с телеграм-ботом
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Проверяет переменные окружения"""
    print("🔍 Проверка переменных окружения...")
    
    load_dotenv()
    
    # Проверяем обязательные переменные
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not telegram_token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
        return False
    
    if not openai_key:
        print("❌ OPENAI_API_KEY не найден в .env")
        return False
    
    # Проверяем формат токенов
    if not telegram_token.startswith(('1', '2', '5', '6', '7')):
        print(f"⚠️  Подозрительный формат Telegram токена: {telegram_token[:10]}...")
    else:
        print(f"✅ Telegram токен: {telegram_token[:10]}...{telegram_token[-5:]}")
    
    if not openai_key.startswith('sk-'):
        print(f"⚠️  Подозрительный формат OpenAI ключа: {openai_key[:10]}...")
    else:
        print(f"✅ OpenAI ключ: {openai_key[:10]}...{openai_key[-5:]}")
    
    return True

async def test_telegram_bot():
    """Тестирует подключение к Telegram Bot API"""
    print("\n🤖 Тестирование Telegram Bot API...")
    
    try:
        from telegram import Bot
        from telegram.error import TelegramError
        
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        bot = Bot(token=token)
        
        # Получаем информацию о боте
        me = await bot.get_me()
        print(f"✅ Бот подключен: @{me.username} ({me.first_name})")
        print(f"   ID: {me.id}")
        print(f"   Может присоединяться к группам: {me.can_join_groups}")
        print(f"   Может читать все сообщения: {me.can_read_all_group_messages}")
        
        # Проверяем webhook
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            print(f"⚠️  Установлен webhook: {webhook_info.url}")
            print("   Для polling нужно удалить webhook!")
        else:
            print("✅ Webhook не установлен (подходит для polling)")
        
        return True
        
    except TelegramError as e:
        print(f"❌ Ошибка Telegram API: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при тестировании Telegram: {e}")
        return False

async def test_openai_api():
    """Тестирует подключение к OpenAI API"""
    print("\n🧠 Тестирование OpenAI API...")
    
    try:
        from openai import OpenAI
        
        api_key = os.getenv('OPENAI_API_KEY')
        client = OpenAI(api_key=api_key)
        
        # Тестируем получение списка моделей
        models = client.models.list()
        print("✅ OpenAI API подключен")
        
        # Проверяем доступность нужной модели
        model_names = [model.id for model in models.data]
        if 'gpt-4o-mini' in model_names:
            print("✅ Модель gpt-4o-mini доступна")
        else:
            print("⚠️  Модель gpt-4o-mini не найдена")
            print(f"   Доступные модели: {model_names[:5]}...")
        
        # Тестируем простой запрос
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Тест"}],
            max_tokens=10
        )
        print("✅ Тестовый запрос к OpenAI выполнен успешно")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка OpenAI API: {e}")
        return False

def test_chroma_db():
    """Тестирует векторную базу данных"""
    print("\n📚 Тестирование Chroma DB...")
    
    try:
        import chromadb
        from langchain_community.vectorstores import Chroma
        from langchain_openai import OpenAIEmbeddings
        
        db_path = "chroma_db_legal_bot_part1"
        
        if not os.path.exists(db_path):
            print(f"❌ База данных не найдена: {db_path}")
            return False
        
        # Проверяем содержимое
        if not os.listdir(db_path):
            print("⚠️  База данных пуста")
            return False
        
        # Тестируем подключение
        embeddings = OpenAIEmbeddings(openai_api_key=os.getenv('OPENAI_API_KEY'))
        vector_store = Chroma(persist_directory=db_path, embedding_function=embeddings)
        
        # Тестируем поиск
        results = vector_store.similarity_search("тест", k=1)
        print(f"✅ Chroma DB работает, найдено документов: {len(results)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка Chroma DB: {e}")
        return False

def test_redis():
    """Тестирует подключение к Redis"""
    print("\n🔴 Тестирование Redis...")
    
    try:
        import redis
        
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        
        # Тестируем подключение
        client.ping()
        print(f"✅ Redis подключен: {redis_url}")
        
        # Тестируем запись/чтение
        client.set("test_key", "test_value", ex=10)
        value = client.get("test_key")
        if value == "test_value":
            print("✅ Redis запись/чтение работает")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Redis недоступен: {e}")
        print("   Бот будет работать без кэширования")
        return True  # Не критично

async def test_bot_handlers():
    """Тестирует инициализацию обработчиков бота"""
    print("\n⚙️ Тестирование обработчиков бота...")
    
    try:
        # Добавляем путь к neuralex-main
        neuralex_path = os.path.join(os.path.dirname(__file__), 'neuralex-main')
        if neuralex_path not in sys.path:
            sys.path.append(neuralex_path)
        
        # Тестируем импорт обработчиков
        from bot.handlers import start, button_handler, handle_user_message, handle_document
        print("✅ Обработчики импортированы")
        
        # Тестируем импорт neuralex
        from neuralex_main import neuralex
        print("✅ Neuralex импортирован")
        
        # Тестируем инициализацию компонентов
        from bot.handlers import law_assistant, analytics, user_manager
        
        if law_assistant:
            print("✅ Law assistant инициализирован")
        else:
            print("❌ Law assistant не инициализирован")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании обработчиков: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Основная функция диагностики"""
    print("🔍 ДИАГНОСТИКА ТЕЛЕГРАМ-БОТА NEURALEX\n")
    
    checks = []
    
    # Проверяем переменные окружения
    checks.append(check_environment())
    
    # Тестируем Telegram API
    checks.append(await test_telegram_bot())
    
    # Тестируем OpenAI API
    checks.append(await test_openai_api())
    
    # Тестируем Chroma DB
    checks.append(test_chroma_db())
    
    # Тестируем Redis
    checks.append(test_redis())
    
    # Тестируем обработчики
    checks.append(await test_bot_handlers())
    
    print("\n" + "="*50)
    print("📊 РЕЗУЛЬТАТЫ ДИАГНОСТИКИ:")
    
    passed = sum(checks)
    total = len(checks)
    
    if passed == total:
        print(f"✅ Все проверки пройдены ({passed}/{total})")
        print("🎉 Бот должен работать корректно!")
        
        print("\n💡 РЕКОМЕНДАЦИИ:")
        print("1. Запустите бота: python run_bot.py")
        print("2. Найдите бота в Telegram по имени")
        print("3. Отправьте /start")
        print("4. Если проблемы остались, проверьте логи")
        
    else:
        print(f"❌ Проблемы обнаружены ({passed}/{total} прошли)")
        print("\n🔧 НЕОБХОДИМЫЕ ДЕЙСТВИЯ:")
        print("1. Исправьте найденные проблемы")
        print("2. Запустите диагностику повторно")
        print("3. Обратитесь к документации")

if __name__ == "__main__":
    asyncio.run(main())