#!/usr/bin/env python3
"""
Простой тест бота для проверки основных функций
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

async def test_openai_direct():
    """Прямой тест OpenAI API"""
    print("🧠 Тестирование OpenAI API напрямую...")
    
    try:
        from openai import OpenAI
        
        api_key = os.getenv('OPENAI_API_KEY')
        client = OpenAI(api_key=api_key)
        
        # Простой тест
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Привет! Ответь одним словом: работаю"}],
            max_tokens=10
        )
        
        answer = response.choices[0].message.content
        print(f"✅ OpenAI ответ: {answer}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка OpenAI: {e}")
        return False

async def test_neuralex_direct():
    """Прямой тест neuralex"""
    print("\n🤖 Тестирование neuralex напрямую...")
    
    try:
        # Добавляем путь к neuralex-main
        neuralex_path = os.path.join(os.path.dirname(__file__), 'neuralex-main')
        if neuralex_path not in sys.path:
            sys.path.append(neuralex_path)
        
        from neuralex_main import neuralex
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from langchain_community.vectorstores import Chroma
        
        openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # Инициализируем компоненты
        llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.9, openai_api_key=openai_api_key)
        embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        vector_store = Chroma(persist_directory="chroma_db_legal_bot_part1", embedding_function=embeddings)
        
        # Создаем neuralex
        law_assistant = neuralex(llm, embeddings, vector_store, None)  # Без Redis
        
        # Тестируем простой вопрос
        test_question = "Что такое Конституция РФ?"
        print(f"Задаем вопрос: {test_question}")
        
        answer, history = law_assistant.conversational(test_question, "test_user")
        
        print(f"✅ Neuralex ответ: {answer[:200]}...")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка neuralex: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_telegram_handlers():
    """Тест обработчиков Telegram"""
    print("\n📱 Тестирование обработчиков Telegram...")
    
    try:
        from bot.handlers import initialize_components
        
        # Проверяем инициализацию
        success = initialize_components()
        if success:
            print("✅ Обработчики инициализированы")
            
            # Проверяем law_assistant
            from bot.handlers import law_assistant
            if law_assistant:
                print("✅ Law assistant доступен")
                return True
            else:
                print("❌ Law assistant не инициализирован")
                return False
        else:
            print("❌ Ошибка инициализации обработчиков")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка обработчиков: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Основная функция тестирования"""
    print("🔍 ПРОСТОЙ ТЕСТ БОТА NEURALEX\n")
    
    load_dotenv()
    
    tests = [
        test_openai_direct(),
        test_neuralex_direct(),
        test_telegram_handlers()
    ]
    
    results = []
    for test in tests:
        result = await test
        results.append(result)
    
    print("\n" + "="*50)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ Все тесты пройдены ({passed}/{total})")
        print("🎉 Бот должен работать!")
        
        print("\n🚀 Запустите бота:")
        print("python run_bot.py")
        
    else:
        print(f"❌ Некоторые тесты не прошли ({passed}/{total})")
        print("🔧 Проверьте ошибки выше")

if __name__ == "__main__":
    asyncio.run(main())