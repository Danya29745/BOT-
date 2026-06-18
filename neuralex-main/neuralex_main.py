import logging
import threading
import time
from openai import OpenAI
from cache import RedisCache
from langchain.schema import HumanMessage, AIMessage
from chains import get_rag_chain
from prompts import SYSTEM_PROMPT, QA_PROMPT

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

class neuralex:
    """
    Conversational AI для юридических консультаций с RAG pipeline
    """
    store = {}
    store_lock = threading.Lock()

    def __init__(self, llm, embeddings, vector_store, redis_url=None):
        self.llm = llm
        self.embeddings = embeddings
        self.vector_store = vector_store
        
        # Инициализируем кэш с внешним Redis клиентом
        redis_client = None
        if redis_url:
            try:
                import redis
                redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
                redis_client.ping()
                logger.info(f"Redis кэш инициализирован: {redis_url}")
            except Exception as e:
                logger.error(f"Ошибка инициализации Redis кэша: {e}")
                redis_client = None
        
        self.cache = RedisCache(redis_client)

    def get_session_history(self, session_id):
        with neuralex.store_lock:
            if session_id not in neuralex.store:
                if self.cache:
                    neuralex.store[session_id] = self.cache.get_chat_history(session_id)
                    logger.info(f"Создана новая история чата для session_id: {session_id}")
                else:
                    # Fallback без Redis
                    from langchain.memory import ChatMessageHistory
                    neuralex.store[session_id] = ChatMessageHistory()
                    logger.warning(f"Создана локальная история чата для session_id: {session_id} (Redis недоступен)")
            else:
                logger.debug(f"Используется существующая история чата для session_id: {session_id}")
        return neuralex.store[session_id]

    def conversational(self, query, session_id):
        """
        Handles a query from a user within a session:
        - Uses Redis-based history for retrieval.
        - Returns cached response if available.
        - Otherwise, runs full RAG pipeline and updates history.

        Returns:
            Tuple[str, list]: (LLM answer, updated message list)
        """
        start_time = time.time()
        
        # Проверяем кэш только если он доступен
        cached_answer = None
        if self.cache:
            try:
                cache_key = self.cache.make_cache_key(query, session_id)
                cached_answer = self.cache.get(cache_key)
                if cached_answer:
                    logger.info(f"Попадание в кэш для ключа: {cache_key}")
                    chat_history = self.get_session_history(session_id).messages
                    return cached_answer, chat_history
            except Exception as e:
                logger.error(f"Ошибка при работе с кэшем: {e}")

        logger.info(f"Промах кэша. Генерируем новый ответ для session_id: {session_id}")

        try:
            rag_chain = get_rag_chain(self.llm, self.vector_store, SYSTEM_PROMPT, QA_PROMPT)

            chat_history_obj = self.get_session_history(session_id)
            messages = chat_history_obj.messages

            logger.debug(f"Отправляем запрос в RAG цепочку для session_id: {session_id}")
            
            response = rag_chain.invoke(
                {"input": query, "chat_history": messages}
            )

            answer = response['answer']
            
            # Логируем использование токенов если доступно
            try:
                # Пытаемся получить информацию о токенах из response
                if hasattr(response, 'response_metadata') and 'token_usage' in response.response_metadata:
                    token_usage = response.response_metadata['token_usage']
                    prompt_tokens = token_usage.get('prompt_tokens', 0)
                    completion_tokens = token_usage.get('completion_tokens', 0)
                    total_tokens = token_usage.get('total_tokens', 0)
                    
                    # Импортируем analytics здесь чтобы избежать циклических импортов
                    try:
                        import sys
                        import os
                        bot_path = os.path.join(os.path.dirname(__file__), '..', 'bot')
                        if bot_path not in sys.path:
                            sys.path.append(bot_path)
                        
                        from analytics import BotAnalytics
                        if self.cache and self.cache.redis_client:
                            analytics = BotAnalytics(self.cache.redis_client)
                            analytics.log_token_usage(session_id, prompt_tokens, completion_tokens, total_tokens)
                    except Exception as analytics_error:
                        logger.debug(f"Не удалось записать токены в аналитику: {analytics_error}")
                        
            except Exception as token_error:
                logger.debug(f"Не удалось получить информацию о токенах: {token_error}")

            # Обновляем историю чата
            chat_history_obj.add_user_message(query)
            chat_history_obj.add_ai_message(answer)

            # Кэшируем ответ, если кэш доступен
            if self.cache:
                try:
                    self.cache.set(cache_key, answer)
                    logger.debug(f"Ответ закэширован для ключа: {cache_key}")
                except Exception as e:
                    logger.error(f"Ошибка при кэшировании ответа: {e}")

            processing_time = time.time() - start_time
            logger.info(f"Запрос обработан за {processing_time:.2f} секунд для session_id: {session_id}")
            
            return answer, chat_history_obj.messages
            
        except Exception as openai_error:
            # Проверяем, является ли это ошибкой OpenAI
            error_str = str(openai_error).lower()
            if any(keyword in error_str for keyword in ['openai', 'api key', 'rate limit', 'quota', 'authentication']):
                logger.error(f"OpenAI API ошибка для session_id {session_id}: {openai_error}")
                # Пробрасываем ошибку OpenAI выше для специальной обработки
                raise openai_error
            else:
                logger.error(f"Общая ошибка при обработке запроса для session_id {session_id}: {openai_error}")
                raise
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса для session_id {session_id}: {e}")
            raise
