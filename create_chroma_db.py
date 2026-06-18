#!/usr/bin/env python3
"""
Скрипт для создания новой базы данных Chroma
"""

import os
from dotenv import load_dotenv

def create_chroma_db():
    """Создает новую базу данных Chroma"""
    load_dotenv()
    
    try:
        from langchain_openai import OpenAIEmbeddings
        from langchain_community.vectorstores import Chroma
        
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            print("❌ OPENAI_API_KEY не найден в .env")
            return False
        
        print("🔄 Создание новой базы данных Chroma...")
        
        # Создаем embeddings
        embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        
        # Создаем новую базу данных
        vector_store = Chroma(
            persist_directory="chroma_db_legal_bot_part1",
            embedding_function=embeddings
        )
        
        # Добавляем тестовый документ
        test_docs = [
            "Конституция Российской Федерации - основной закон государства",
            "Гражданский кодекс РФ регулирует имущественные отношения",
            "Уголовный кодекс РФ определяет преступления и наказания"
        ]
        
        vector_store.add_texts(test_docs)
        
        print("✅ База данных Chroma создана успешно")
        print(f"📊 Добавлено {len(test_docs)} тестовых документов")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при создании базы данных: {e}")
        return False

if __name__ == "__main__":
    create_chroma_db()