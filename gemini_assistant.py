"""
gemini_assistant.py — замена neuralex на Google Gemini API (бесплатный tier).
Поддерживает: текст, PDF, DOCX, изображения, историю чата.
Интерфейс идентичен neuralex: conversational(query, session_id) → (answer, messages)
"""

import logging
import threading
import time
import base64
import os
import tempfile
import google.generativeai as genai
from pathlib import Path

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# СИСТЕМНЫЙ ПРОМПТ — редактируй здесь
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
Ты — бот @LegalHelpRU_bot, помощник по юридическим вопросам на основе российского законодательства.

⚠️ ВАЖНЫЙ ДИСКЛЕЙМЕР — добавляй в начало каждого ответа на юридический вопрос:
«Я бот, не дипломированный юрист. Мои ответы носят исключительно информационный характер и не являются официальной юридической консультацией. Я не несу ответственности за последствия принятых на их основе решений. По серьёзным вопросам обращайтесь к квалифицированному юристу.»

ТВОЯ ЛИЧНОСТЬ:
- Ты бот @LegalHelpRU_bot — дружелюбный и профессиональный помощник
- Ты НЕ юрист, ты ИИ-помощник, и всегда честно об этом говоришь
- Отвечаешь только на русском языке
- Используешь простой, понятный язык без лишних юридических терминов
- Всегда ссылаешься на конкретные статьи законов РФ, если они есть
- Помнишь историю разговора и учитываешь контекст предыдущих вопросов

СТРУКТУРА ОТВЕТА НА ЮРИДИЧЕСКИЙ ВОПРОС:

⚠️ Дисклеймер (кратко)

🎯 Краткий ответ: суть в 1–2 предложениях

📋 Подробнее: развёрнутое объяснение простыми словами

⚖️ Правовая база: конкретные статьи и законы (если применимо)

🔍 Практические шаги: что делать (если применимо)

💡 Важно знать: ключевые нюансы и риски

ЗАКОНОДАТЕЛЬНАЯ БАЗА:
Конституция РФ, ГК РФ, УК РФ, КоАП РФ, ТК РФ, СК РФ, НК РФ, ГПК РФ, УПК РФ, АПК РФ, ЖК РФ, ЗК РФ, ФЗ «О защите прав потребителей», ФЗ «О персональных данных» и другие федеральные законы.

ПРАВИЛА:
- Если вопрос не юридический — вежливо направь к юридическим вопросам
- Если информации нет — честно признай и посоветуй обратиться к юристу
- Никогда не выдавай себя за человека или дипломированного юриста
- Не давай советов по обходу закона
- Отвечай ТОЛЬКО на русском языке
"""

DOCUMENT_ANALYSIS_PROMPT = """
Проанализируй приложенный документ на соответствие российскому законодательству.

⚠️ Я бот, не юрист. Анализ носит информационный характер.

Структура анализа:
📋 Общая оценка: ✅ Соответствует / ⚠️ Частично / ❌ Не соответствует
🔍 Чеклист обязательных элементов документа
⚖️ Соответствие законодательству РФ
🚨 Выявленные проблемы и риски
🔧 Рекомендации по исправлению (со ссылками на статьи)
💡 Практические советы
🎯 Итоговое заключение

Используй простой понятный язык, объясняй термины.
"""


class GeminiAssistant:
    """
    ИИ-помощник на базе Google Gemini.
    Поддерживает текст, PDF, DOCX, изображения.
    Совместимый интерфейс с neuralex.
    """

    _store: dict = {}
    _lock = threading.Lock()

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash",
                 redis_url: str = None, vector_store=None):
        genai.configure(api_key=api_key)
        self.model_name = model
        self.vector_store = vector_store  # опционально, для RAG

        # Конфигурация генерации
        self.generation_config = genai.types.GenerationConfig(
            max_output_tokens=2048,
            temperature=0.7,
        )

        # Инициализация модели
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
            system_instruction=SYSTEM_PROMPT,
        )

        # Опциональный Redis
        self._redis = None
        if redis_url:
            try:
                import redis as _redis
                r = _redis.Redis.from_url(redis_url, decode_responses=True)
                r.ping()
                self._redis = r
                logger.info("✅ Redis подключён")
            except Exception as e:
                logger.warning(f"⚠️ Redis недоступен: {e}")

        logger.info(f"✅ GeminiAssistant инициализирован (модель: {self.model_name})")

    # ─── История ─────────────────────────────────────────────────────────────

    def get_session_history(self, session_id: str) -> list:
        with self._lock:
            if session_id not in self._store:
                history = []
                if self._redis:
                    try:
                        import json
                        raw = self._redis.get(f"chat:{session_id}")
                        if raw:
                            history = json.loads(raw)
                    except Exception:
                        pass
                self._store[session_id] = history
        return self._store[session_id]

    def _save_history(self, session_id: str):
        if self._redis:
            try:
                import json
                data = json.dumps(self._store.get(session_id, []), ensure_ascii=False)
                self._redis.setex(f"chat:{session_id}", 86400 * 7, data)
            except Exception as e:
                logger.debug(f"Не удалось сохранить историю: {e}")

    def clear_history(self, session_id: str):
        with self._lock:
            self._store.pop(session_id, None)
        if self._redis:
            try:
                self._redis.delete(f"chat:{session_id}")
            except Exception:
                pass

    # ─── RAG поиск ───────────────────────────────────────────────────────────

    def _get_context(self, query: str, k: int = 3) -> str:
        if not self.vector_store:
            return ""
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            return "\n\n".join(doc.page_content for doc in docs)
        except Exception as e:
            logger.warning(f"RAG поиск недоступен: {e}")
            return ""

    # ─── Основной метод ──────────────────────────────────────────────────────

    def conversational(self, query: str, session_id: str, file_bytes: bytes = None,
                       file_mime: str = None):
        """
        query       — текст пользователя
        session_id  — ID пользователя/сессии
        file_bytes  — байты файла (PDF, DOCX, изображение) — опционально
        file_mime   — MIME-тип файла, напр. 'application/pdf'

        Возвращает (answer: str, history: list) — совместимо с neuralex
        """
        start = time.time()

        history = self.get_session_history(session_id)

        # Формат истории для Gemini: [{"role": "user"/"model", "parts": [...]}]
        gemini_history = []
        for msg in history:
            role = "model" if msg.get("role") == "assistant" else "user"
            gemini_history.append({"role": role, "parts": [msg.get("content", "")]})

        # Запускаем чат с историей
        chat = self.model.start_chat(history=gemini_history)

        # Формируем сообщение
        parts = []

        # Добавляем RAG-контекст если нет файла
        if not file_bytes:
            context = self._get_context(query)
            if context:
                parts.append(f"КОНТЕКСТ ИЗ БАЗЫ ЗАКОНОВ:\n{context}\n\n")

        parts.append(query)

        # Добавляем файл если есть
        if file_bytes and file_mime:
            try:
                # Gemini принимает файлы через upload API
                with tempfile.NamedTemporaryFile(delete=False, suffix=self._ext(file_mime)) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name

                uploaded = genai.upload_file(tmp_path, mime_type=file_mime)
                parts = [uploaded, query if query else DOCUMENT_ANALYSIS_PROMPT]
                os.unlink(tmp_path)
                logger.info(f"✅ Файл загружен в Gemini: {file_mime}")
            except Exception as e:
                logger.warning(f"Ошибка загрузки файла в Gemini: {e}")
                # Fallback: добавляем текст что файл не удалось обработать
                parts.append("\n[Не удалось обработать прикреплённый файл]")

        try:
            response = chat.send_message(parts)
            answer = response.text

            # Обновляем историю
            with self._lock:
                self._store.setdefault(session_id, [])
                self._store[session_id].append({"role": "user", "content": query or "Анализ документа"})
                self._store[session_id].append({"role": "assistant", "content": answer})
                # Хранить максимум 20 сообщений (10 пар)
                if len(self._store[session_id]) > 20:
                    self._store[session_id] = self._store[session_id][-20:]

            self._save_history(session_id)

            elapsed = time.time() - start
            logger.info(f"✅ Ответ за {elapsed:.2f}с для {session_id}")

            return answer, self.get_session_history(session_id)

        except Exception as e:
            logger.error(f"❌ Ошибка Gemini API для {session_id}: {e}")
            raise

    def analyze_document(self, document_text: str, session_id: str,
                         file_bytes: bytes = None, file_mime: str = None) -> str:
        """
        Анализирует юридический документ.
        Принимает либо текст (document_text), либо файл (file_bytes + file_mime).
        """
        if file_bytes and file_mime:
            answer, _ = self.conversational(
                DOCUMENT_ANALYSIS_PROMPT,
                session_id,
                file_bytes=file_bytes,
                file_mime=file_mime
            )
        else:
            prompt = DOCUMENT_ANALYSIS_PROMPT + f"\n\nТЕКСТ ДОКУМЕНТА:\n{document_text[:8000]}"
            answer, _ = self.conversational(prompt, session_id)
        return answer

    @staticmethod
    def _ext(mime: str) -> str:
        return {
            "application/pdf": ".pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "text/plain": ".txt",
            "image/jpeg": ".jpg",
            "image/png": ".png",
        }.get(mime, ".bin")

    # ─── Совместимость с neuralex ─────────────────────────────────────────────

    def rate_last_answer(self, session_id: str, rating: int) -> bool:
        if self._redis:
            try:
                self._redis.lpush(f"ratings:{session_id}", rating)
                return True
            except Exception:
                pass
        return False
