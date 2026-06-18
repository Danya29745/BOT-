"""
gemini_assistant.py — ИИ-ассистент на базе OpenRouter API.
Совместимый интерфейс с neuralex: conversational(query, session_id) → (answer, history)
"""

import logging
import threading
import time
import os
from openai import OpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Ты — бот @LegalHelpRU_bot, помощник по юридическим вопросам на основе российского законодательства.

ВАЖНЫЙ ДИСКЛЕЙМЕР — добавляй в начало каждого ответа на юридический вопрос:
«Я бот, не дипломированный юрист. Мои ответы носят исключительно информационный характер и не являются официальной юридической консультацией. Я не несу ответственности за последствия принятых на их основе решений. По серьёзным вопросам обращайтесь к квалифицированному юристу.»

ТВОЯ ЛИЧНОСТЬ:
- Ты бот @LegalHelpRU_bot — дружелюбный и профессиональный помощник
- Ты НЕ юрист, ты ИИ-помощник, и всегда честно об этом говоришь
- Отвечаешь только на русском языке
- Используешь простой, понятный язык без лишних юридических терминов
- Всегда ссылаешься на конкретные статьи законов РФ, если они есть
- Помнишь историю разговора и учитываешь контекст предыдущих вопросов

СТРУКТУРА ОТВЕТА НА ЮРИДИЧЕСКИЙ ВОПРОС:

Дисклеймер (кратко)

Краткий ответ: суть в 1-2 предложениях

Подробнее: развёрнутое объяснение простыми словами

Правовая база: конкретные статьи и законы (если применимо)

Практические шаги: что делать (если применимо)

Важно знать: ключевые нюансы и риски

ЗАКОНОДАТЕЛЬНАЯ БАЗА:
Конституция РФ, ГК РФ, УК РФ, КоАП РФ, ТК РФ, СК РФ, НК РФ, ГПК РФ, УПК РФ, АПК РФ, ЖК РФ, ЗК РФ, ФЗ О защите прав потребителей, ФЗ О персональных данных и другие федеральные законы.

ПРАВИЛА:
- Если вопрос не юридический — вежливо направь к юридическим вопросам
- Если информации нет — честно признай и посоветуй обратиться к юристу
- Никогда не выдавай себя за человека или дипломированного юриста
- Не давай советов по обходу закона
- Отвечай ТОЛЬКО на русском языке
"""

DOCUMENT_ANALYSIS_PROMPT = """
Проанализируй приложенный документ на соответствие российскому законодательству.

Я бот, не юрист. Анализ носит информационный характер.

Структура анализа:
Общая оценка: Соответствует / Частично / Не соответствует
Чеклист обязательных элементов документа
Соответствие законодательству РФ
Выявленные проблемы и риски
Рекомендации по исправлению (со ссылками на статьи)
Практические советы
Итоговое заключение

Используй простой понятный язык, объясняй термины.
"""


class GeminiAssistant:
    """
    ИИ-помощник на базе OpenRouter (совместимый интерфейс с neuralex).
    """

    _store: dict = {}
    _lock = threading.Lock()

    def __init__(self, api_key: str, model: str = "meta-llama/llama-3.3-70b-instruct:free",
                 redis_url: str = None, vector_store=None):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model_name = model
        self.vector_store = vector_store

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

    def conversational(self, query: str, session_id: str,
                       file_bytes: bytes = None, file_mime: str = None):
        """
        Возвращает (answer: str, history: list)
        """
        start = time.time()
        history = self.get_session_history(session_id)

        # Формируем messages для OpenAI-совместимого API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Добавляем историю
        for msg in history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        # Текущий запрос
        user_content = query or DOCUMENT_ANALYSIS_PROMPT

        # RAG-контекст
        if not file_bytes:
            context = self._get_context(query)
            if context:
                user_content = f"КОНТЕКСТ ИЗ БАЗЫ ЗАКОНОВ:\n{context}\n\n{user_content}"

        # Файл — конвертируем в base64 и добавляем как текст (OpenRouter поддерживает vision)
        if file_bytes and file_mime and file_mime.startswith("image/"):
            import base64
            b64 = base64.b64encode(file_bytes).decode()
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{file_mime};base64,{b64}"}},
                    {"type": "text", "text": user_content}
                ]
            })
        else:
            # Для PDF/DOCX — извлекаем текст и добавляем как текст
            if file_bytes and file_mime:
                extracted = self._extract_text(file_bytes, file_mime)
                if extracted:
                    user_content = f"{DOCUMENT_ANALYSIS_PROMPT}\n\nТЕКСТ ДОКУМЕНТА:\n{extracted[:8000]}"
                else:
                    user_content += "\n[Не удалось прочитать файл — отправьте текст вручную]"
            messages.append({"role": "user", "content": user_content})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=2048,
                temperature=0.7,
            )
            answer = response.choices[0].message.content

            # Обновляем историю
            with self._lock:
                self._store.setdefault(session_id, [])
                self._store[session_id].append({"role": "user", "content": query or "Анализ документа"})
                self._store[session_id].append({"role": "assistant", "content": answer})
                if len(self._store[session_id]) > 20:
                    self._store[session_id] = self._store[session_id][-20:]

            self._save_history(session_id)

            elapsed = time.time() - start
            logger.info(f"✅ Ответ за {elapsed:.2f}с для {session_id}")

            return answer, self.get_session_history(session_id)

        except Exception as e:
            logger.error(f"❌ Ошибка OpenRouter API для {session_id}: {e}")
            raise

    def _extract_text(self, file_bytes: bytes, mime_type: str) -> str:
        """Извлекает текст из PDF или DOCX"""
        try:
            if mime_type == "application/pdf":
                import fitz  # PyMuPDF
                import tempfile, os
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name
                doc = fitz.open(tmp_path)
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                os.unlink(tmp_path)
                return text
            elif "wordprocessingml" in mime_type or mime_type == "application/msword":
                import docx
                import tempfile, os, io
                doc = docx.Document(io.BytesIO(file_bytes))
                return "\n".join(p.text for p in doc.paragraphs)
            elif mime_type == "text/plain":
                return file_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Ошибка извлечения текста из файла: {e}")
        return ""

    def analyze_document(self, document_text: str, session_id: str,
                         file_bytes: bytes = None, file_mime: str = None) -> str:
        if file_bytes and file_mime:
            answer, _ = self.conversational(
                DOCUMENT_ANALYSIS_PROMPT, session_id,
                file_bytes=file_bytes, file_mime=file_mime
            )
        else:
            prompt = DOCUMENT_ANALYSIS_PROMPT + f"\n\nТЕКСТ ДОКУМЕНТА:\n{document_text[:8000]}"
            answer, _ = self.conversational(prompt, session_id)
        return answer

    def rate_last_answer(self, session_id: str, rating: int) -> bool:
        if self._redis:
            try:
                self._redis.lpush(f"ratings:{session_id}", rating)
                return True
            except Exception:
                pass
        return False
ENDOFFILE
echo "done"
