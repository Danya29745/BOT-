"""
Менеджер состояний пользователей
"""
import logging
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class StateManager:
    """Менеджер для управления состояниями пользователей"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self._local_states = {}  # Fallback для локального хранения
        self._last_answers = {}  # Хранение последних ответов для оценки
        self._suggested_questions = {}  # Хранение предложенных вопросов
        self._consultations = {}  # Локальное хранилище сохраненных консультаций
    
    def set_user_state(self, user_id: str, state: str):
        """Устанавливает состояние пользователя"""
        try:
            if self.redis_client:
                self.redis_client.setex(f"user_state:{user_id}", 3600, state)  # TTL 1 час
            else:
                self._local_states[user_id] = state
            logger.debug(f"Состояние пользователя {user_id} установлено: {state}")
        except Exception as e:
            logger.error(f"Ошибка при установке состояния пользователя {user_id}: {e}")
            self._local_states[user_id] = state
    
    def get_user_state(self, user_id: str) -> Optional[str]:
        """Получает состояние пользователя"""
        try:
            if self.redis_client:
                state = self.redis_client.get(f"user_state:{user_id}")
                return state
            else:
                return self._local_states.get(user_id)
        except Exception as e:
            logger.error(f"Ошибка при получении состояния пользователя {user_id}: {e}")
            return self._local_states.get(user_id)
    
    def clear_user_state(self, user_id: str):
        """Очищает состояние пользователя"""
        try:
            if self.redis_client:
                self.redis_client.delete(f"user_state:{user_id}")
            if user_id in self._local_states:
                del self._local_states[user_id]
            logger.debug(f"Состояние пользователя {user_id} очищено")
        except Exception as e:
            logger.error(f"Ошибка при очистке состояния пользователя {user_id}: {e}")
    
    def save_last_answer(self, user_id: str, question: str, answer: str):
        """Сохраняет последний ответ для возможной оценки"""
        answer_data = {
            'question': question,
            'answer': answer,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            if self.redis_client:
                import json
                self.redis_client.setex(
                    f"last_answer:{user_id}", 
                    3600,  # TTL 1 час
                    json.dumps(answer_data, ensure_ascii=False)
                )
            else:
                self._last_answers[user_id] = answer_data
            logger.debug(f"Последний ответ сохранен для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении ответа для пользователя {user_id}: {e}")
            self._last_answers[user_id] = answer_data
    
    def get_last_answer(self, user_id: str) -> Optional[Dict]:
        """Получает последний ответ пользователя"""
        try:
            if self.redis_client:
                import json
                data = self.redis_client.get(f"last_answer:{user_id}")
                if data:
                    return json.loads(data)
            else:
                return self._last_answers.get(user_id)
        except Exception as e:
            logger.error(f"Ошибка при получении последнего ответа пользователя {user_id}: {e}")
            return self._last_answers.get(user_id)
    
    def clear_last_answer(self, user_id: str):
        """Удаляет последний ответ пользователя"""
        try:
            if self.redis_client:
                self.redis_client.delete(f"last_answer:{user_id}")
            if user_id in self._last_answers:
                del self._last_answers[user_id]
            logger.debug(f"Последний ответ удален для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при удалении последнего ответа пользователя {user_id}: {e}")

    # -------- Сохраненные консультации --------
    def save_consultation(self, user_id: str, title: str, question: str, answer: str) -> str:
        """Сохраняет консультацию и возвращает ее ID"""
        from datetime import datetime
        import json
        import uuid
        consult_id = uuid.uuid4().hex[:12]
        data = {
            'id': consult_id,
            'title': title[:80] if title else question[:80],
            'question': question,
            'answer': answer,
            'created_at': datetime.now().isoformat()
        }
        try:
            if self.redis_client:
                key = f"consultations:{user_id}"
                # Храним как словарь id->json
                existing = self.redis_client.get(key)
                items = {}
                if existing:
                    try:
                        items = json.loads(existing)
                    except Exception:
                        items = {}
                items[consult_id] = data
                self.redis_client.set(key, json.dumps(items, ensure_ascii=False))
            else:
                self._consultations.setdefault(user_id, {})[consult_id] = data
            return consult_id
        except Exception as e:
            logger.error(f"Ошибка сохранения консультации {user_id}: {e}")
            self._consultations.setdefault(user_id, {})[consult_id] = data
            return consult_id

    def list_consultations(self, user_id: str):
        """Возвращает список консультаций (метаданные)"""
        import json
        try:
            if self.redis_client:
                data = self.redis_client.get(f"consultations:{user_id}")
                if data:
                    items = json.loads(data)
                    return sorted(items.values(), key=lambda x: x.get('created_at',''), reverse=True)
                return []
            return sorted(self._consultations.get(user_id, {}).values(), key=lambda x: x.get('created_at',''), reverse=True)
        except Exception as e:
            logger.error(f"Ошибка получения списка консультаций {user_id}: {e}")
            return sorted(self._consultations.get(user_id, {}).values(), key=lambda x: x.get('created_at',''), reverse=True)

    def get_consultation(self, user_id: str, consult_id: str):
        """Возвращает консультацию по ID"""
        import json
        try:
            if self.redis_client:
                data = self.redis_client.get(f"consultations:{user_id}")
                if data:
                    items = json.loads(data)
                    return items.get(consult_id)
                return None
            return self._consultations.get(user_id, {}).get(consult_id)
        except Exception as e:
            logger.error(f"Ошибка получения консультации {user_id}:{consult_id}: {e}")
            return self._consultations.get(user_id, {}).get(consult_id)

    def delete_consultation(self, user_id: str, consult_id: str) -> bool:
        """Удаляет консультацию по ID"""
        import json
        try:
            if self.redis_client:
                key = f"consultations:{user_id}"
                data = self.redis_client.get(key)
                items = {}
                if data:
                    items = json.loads(data)
                if consult_id in items:
                    del items[consult_id]
                    self.redis_client.set(key, json.dumps(items, ensure_ascii=False))
                    return True
                return False
            if user_id in self._consultations and consult_id in self._consultations[user_id]:
                del self._consultations[user_id][consult_id]
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления консультации {user_id}:{consult_id}: {e}")
            return False

    # -------- Предложенные вопросы --------
    def save_suggested_questions(self, user_id: str, questions: list):
        """Сохраняет список связанных вопросов для быстрых кнопок"""
        try:
            if self.redis_client:
                import json
                self.redis_client.setex(
                    f"suggested_q:{user_id}",
                    1800,  # 30 минут
                    json.dumps(questions, ensure_ascii=False)
                )
            else:
                self._suggested_questions[user_id] = questions
        except Exception as e:
            logger.error(f"Ошибка сохранения предложенных вопросов {user_id}: {e}")
            self._suggested_questions[user_id] = questions

    def get_suggested_question(self, user_id: str, index: int):
        """Возвращает предложенный вопрос по индексу"""
        try:
            questions = None
            if self.redis_client:
                import json
                data = self.redis_client.get(f"suggested_q:{user_id}")
                if data:
                    questions = json.loads(data)
            else:
                questions = self._suggested_questions.get(user_id)
            if not questions:
                return None
            if 0 <= index < len(questions):
                return questions[index]
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении предложенного вопроса {user_id}: {e}")
            return None