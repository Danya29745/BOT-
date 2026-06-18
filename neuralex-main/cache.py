import logging
import redis
import hashlib
from langchain_community.chat_message_histories import RedisChatMessageHistory

logger = logging.getLogger(__name__)

class RedisCache:
    """
    Кэш для LLM ответов и истории чатов с использованием Redis
    """
    
    def __init__(self, redis_client=None, redis_url=None):
        self.redis_client = redis_client
        self.redis_url = redis_url

    def make_cache_key(self, query, session_id):
        key_raw = f"{session_id}:{query}"
        return "llm_cache:" + hashlib.sha256(key_raw.encode()).hexdigest()

    def get(self, key):
        if not self.redis_client:
            return None
        try:
            value = self.redis_client.get(key)
            return value if value else None
        except Exception as e:
            logger.error(f"Ошибка при получении значения из кэша для ключа {key}: {e}")
            return None

    def set(self, key: str, value: str, ttl: int = None) -> None:
        if not self.redis_client:
            return
        try:
            if ttl is not None:
                self.redis_client.setex(key, ttl, value)
            else:
                self.redis_client.set(key, value)
            logger.debug(f"Значение сохранено в кэш для ключа: {key}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении значения в кэш для ключа {key}: {e}")

    def get_chat_history(self, session_id):
        if not self.redis_client:
            # Fallback на локальную историю
            from langchain_community.chat_message_histories import ChatMessageHistory
            return ChatMessageHistory()
        try:
            return RedisChatMessageHistory(session_id=session_id, url=self.redis_url or "redis://localhost:6379/0")
        except Exception as e:
            logger.error(f"Ошибка при создании истории чата для session_id {session_id}: {e}")
