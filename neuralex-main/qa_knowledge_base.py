"""
Система накопления знаний из диалогов пользователей
"""
import logging
import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from langchain.schema import Document
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)

@dataclass
class QAEntry:
    """Структура для хранения пары вопрос-ответ"""
    id: str
    question: str
    answer: str
    sources: List[str]
    tags: List[str]
    rating: float
    rating_count: int
    created_at: str
    last_used: str
    usage_count: int
    session_ids: List[str]  # Кто задавал этот вопрос
    
    def to_dict(self) -> Dict:
        """Конвертирует в словарь для сохранения"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'QAEntry':
        """Создает объект из словаря"""
        return cls(**data)

class QAKnowledgeBase:
    """Класс для управления базой знаний вопросов и ответов"""
    
    def __init__(self, embeddings: OpenAIEmbeddings, redis_client=None, 
                 persist_directory: str = "qa_knowledge_base"):
        self.embeddings = embeddings
        self.redis_client = redis_client
        self.persist_directory = persist_directory
        
        # Инициализируем векторную базу для QA
        try:
            self.vector_store = Chroma(
                persist_directory=persist_directory,
                embedding_function=embeddings,
                collection_name="qa_knowledge"
            )
            logger.info(f"QA Knowledge Base инициализирована: {persist_directory}")
        except Exception as e:
            logger.error(f"Ошибка инициализации QA Knowledge Base: {e}")
            self.vector_store = None
    
    def _generate_qa_id(self, question: str) -> str:
        """Генерирует уникальный ID для пары вопрос-ответ"""
        timestamp = str(int(time.time()))
        question_hash = hashlib.md5(question.encode()).hexdigest()[:8]
        return f"qa_{timestamp}_{question_hash}"
    
    def _extract_tags(self, question: str, answer: str) -> List[str]:
        """Извлекает теги из вопроса и ответа"""
        # Простая система тегов на основе ключевых слов
        legal_keywords = {
            'увольнение': ['уволь', 'увольн', 'расторж', 'работ'],
            'трудовое_право': ['труд', 'работ', 'зарплат', 'отпуск'],
            'семейное_право': ['брак', 'развод', 'алимент', 'семь'],
            'гражданское_право': ['договор', 'собственност', 'наследств'],
            'уголовное_право': ['преступлен', 'наказан', 'уголовн'],
            'административное': ['штраф', 'админ', 'нарушен'],
            'жилищное_право': ['квартир', 'дом', 'жилищ', 'аренд'],
            'налоговое_право': ['налог', 'ндфл', 'декларац']
        }
        
        text = (question + ' ' + answer).lower()
        tags = []
        
        for tag, keywords in legal_keywords.items():
            if any(keyword in text for keyword in keywords):
                tags.append(tag)
        
        return tags[:5]  # Максимум 5 тегов
    
    def find_similar_qa(self, question: str, similarity_threshold: float = 0.85,
                       min_rating: float = 4.0) -> Optional[QAEntry]:
        """
        Ищет похожий вопрос в базе знаний
        
        Args:
            question: Вопрос пользователя
            similarity_threshold: Минимальный порог схожести (0.0-1.0)
            min_rating: Минимальный рейтинг ответа
            
        Returns:
            QAEntry если найден подходящий ответ, иначе None
        """
        if not self.vector_store:
            return None
        
        try:
            # Ищем похожие вопросы (без встроенного порога) и фильтруем вручную
            similar_docs = []
            try:
                # Предпочтительно: получить релевантность 0..1 (выше — лучше)
                pairs = self.vector_store.similarity_search_with_relevance_scores(question, k=5)
                for doc, rel in pairs:
                    similar_docs.append((doc, float(rel)))
            except Exception:
                # Фоллбек: методы могут возвращать расстояние/скор
                pairs = self.vector_store.similarity_search_with_score(question, k=5)
                similar_docs = []
                for doc, score in pairs:
                    try:
                        # Если score — расстояние 0..1 (меньше — ближе), конвертируем в релевантность
                        rel = max(0.0, min(1.0, 1.0 - float(score)))
                    except Exception:
                        rel = 0.0
                    similar_docs.append((doc, rel))
                

            for doc, relevance in similar_docs:
                try:
                    # Получаем полную информацию о QA из метаданных
                    qa_data = json.loads(doc.metadata.get('qa_data', '{}'))
                    qa_entry = QAEntry.from_dict(qa_data)
                    
                    # Порог схожести и качества ответа
                    if relevance >= similarity_threshold and qa_entry.rating >= min_rating:
                        # Обновляем статистику использования
                        self._update_usage_stats(qa_entry.id)
                        
                        logger.info(f"Найден похожий вопрос (relevance: {relevance:.3f}, rating: {qa_entry.rating})")
                        return qa_entry
                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке найденного QA: {e}")
                    continue
            
            logger.debug(f"Похожие вопросы не найдены для: {question[:50]}...")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при поиске похожих вопросов: {e}")
            return None
    
    def save_qa_pair(self, question: str, answer: str, sources: List[str] = None,
                    session_id: str = None, initial_rating: float = 3.0) -> str:
        """
        Сохраняет новую пару вопрос-ответ в базу знаний
        
        Args:
            question: Вопрос пользователя
            answer: Ответ системы
            sources: Источники информации
            session_id: ID сессии пользователя
            initial_rating: Начальный рейтинг
            
        Returns:
            ID созданной записи
        """
        if not self.vector_store:
            logger.warning("Vector store недоступен, QA не сохранен")
            return None
        
        try:
            # Создаем QA запись
            qa_id = self._generate_qa_id(question)
            current_time = datetime.now().isoformat()
            
            qa_entry = QAEntry(
                id=qa_id,
                question=question,
                answer=answer,
                sources=sources or [],
                tags=self._extract_tags(question, answer),
                rating=initial_rating,
                rating_count=0,
                created_at=current_time,
                last_used=current_time,
                usage_count=1,
                session_ids=[session_id] if session_id else []
            )
            
            # Сохраняем в векторную базу
            metadata = {
                'qa_id': qa_id,
                'qa_data': json.dumps(qa_entry.to_dict(), ensure_ascii=False),
                'tags': ','.join(qa_entry.tags),
                'rating': qa_entry.rating,
                'created_at': current_time
            }
            
            self.vector_store.add_texts(
                texts=[question],
                metadatas=[metadata],
                ids=[qa_id]
            )
            
            # Сохраняем в Redis для быстрого доступа
            if self.redis_client:
                try:
                    self.redis_client.setex(
                        f"qa:{qa_id}",
                        30 * 24 * 3600,  # TTL 30 дней
                        json.dumps(qa_entry.to_dict(), ensure_ascii=False)
                    )
                except Exception as e:
                    logger.error(f"Ошибка сохранения QA в Redis: {e}")
            
            logger.info(f"QA пара сохранена: {qa_id} (теги: {qa_entry.tags})")
            return qa_id
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении QA пары: {e}")
            return None
    
    def update_rating(self, qa_id: str, new_rating: int) -> bool:
        """
        Обновляет рейтинг ответа
        
        Args:
            qa_id: ID записи QA
            new_rating: Новая оценка (1-5)
            
        Returns:
            True если обновление успешно
        """
        try:
            # Получаем текущую запись
            qa_entry = self._get_qa_by_id(qa_id)
            if not qa_entry:
                logger.warning(f"QA запись не найдена: {qa_id}")
                return False
            
            # Обновляем рейтинг (скользящее среднее)
            current_total = qa_entry.rating * qa_entry.rating_count
            new_total = current_total + new_rating
            qa_entry.rating_count += 1
            qa_entry.rating = new_total / qa_entry.rating_count
            
            # Сохраняем обновленную запись
            self._update_qa_entry(qa_entry)
            
            logger.info(f"Рейтинг обновлен для {qa_id}: {qa_entry.rating:.2f} ({qa_entry.rating_count} оценок)")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении рейтинга: {e}")
            return False
    
    def _get_qa_by_id(self, qa_id: str) -> Optional[QAEntry]:
        """Получает QA запись по ID"""
        try:
            # Сначала пробуем Redis
            if self.redis_client:
                data = self.redis_client.get(f"qa:{qa_id}")
                if data:
                    return QAEntry.from_dict(json.loads(data))
            
            # Если в Redis нет, ищем в векторной базе
            if self.vector_store:
                docs = self.vector_store.get(ids=[qa_id])
                if docs and docs['documents']:
                    metadata = docs['metadatas'][0]
                    qa_data = json.loads(metadata.get('qa_data', '{}'))
                    return QAEntry.from_dict(qa_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении QA по ID {qa_id}: {e}")
            return None
    
    def _update_qa_entry(self, qa_entry: QAEntry):
        """Обновляет QA запись в базах данных"""
        try:
            # Обновляем в Redis
            if self.redis_client:
                self.redis_client.setex(
                    f"qa:{qa_entry.id}",
                    30 * 24 * 3600,
                    json.dumps(qa_entry.to_dict(), ensure_ascii=False)
                )
            
            # Обновляем метаданные в векторной базе
            if self.vector_store:
                try:
                    metadata = {
                        'qa_id': qa_entry.id,
                        'qa_data': json.dumps(qa_entry.to_dict(), ensure_ascii=False),
                        'tags': ','.join(qa_entry.tags),
                        'rating': qa_entry.rating,
                        'created_at': qa_entry.created_at
                    }
                    
                    # Для Chroma проще пересоздать запись
                    # Удаляем старую и добавляем новую
                    try:
                        self.vector_store.delete(ids=[qa_entry.id])
                    except Exception:
                        pass  # Игнорируем если запись не найдена
                    
                    self.vector_store.add_texts(
                        texts=[qa_entry.question],
                        metadatas=[metadata],
                        ids=[qa_entry.id]
                    )
                except Exception as e:
                    logger.error(f"Ошибка обновления в векторной базе: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении QA записи: {e}")
    
    def _update_usage_stats(self, qa_id: str):
        """Обновляет статистику использования QA записи"""
        try:
            qa_entry = self._get_qa_by_id(qa_id)
            if qa_entry:
                qa_entry.usage_count += 1
                qa_entry.last_used = datetime.now().isoformat()
                self._update_qa_entry(qa_entry)
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении статистики использования: {e}")
    
    def get_popular_questions(self, limit: int = 10) -> List[QAEntry]:
        """Возвращает самые популярные вопросы"""
        try:
            if not self.redis_client:
                return []
            
            # Получаем все QA записи из Redis
            qa_keys = self.redis_client.keys("qa:*")
            qa_entries = []
            
            for key in qa_keys[:100]:  # Ограничиваем для производительности
                try:
                    data = self.redis_client.get(key)
                    if data:
                        qa_entry = QAEntry.from_dict(json.loads(data))
                        qa_entries.append(qa_entry)
                except Exception:
                    continue
            
            # Сортируем по популярности (usage_count * rating)
            qa_entries.sort(key=lambda x: x.usage_count * x.rating, reverse=True)
            return qa_entries[:limit]
            
        except Exception as e:
            logger.error(f"Ошибка при получении популярных вопросов: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Возвращает статистику базы знаний"""
        try:
            stats = {
                'total_qa_pairs': 0,
                'average_rating': 0.0,
                'total_usage': 0,
                'popular_tags': {},
                'recent_additions': 0
            }
            
            if not self.redis_client:
                return stats
            
            qa_keys = self.redis_client.keys("qa:*")
            stats['total_qa_pairs'] = len(qa_keys)
            
            if qa_keys:
                total_rating = 0
                total_usage = 0
                tag_counts = {}
                recent_count = 0
                week_ago = datetime.now() - timedelta(days=7)
                
                for key in qa_keys[:100]:  # Ограничиваем для производительности
                    try:
                        data = self.redis_client.get(key)
                        if data:
                            qa_entry = QAEntry.from_dict(json.loads(data))
                            total_rating += qa_entry.rating
                            total_usage += qa_entry.usage_count
                            
                            # Считаем теги
                            for tag in qa_entry.tags:
                                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                            
                            # Считаем недавние добавления
                            created_date = datetime.fromisoformat(qa_entry.created_at)
                            if created_date >= week_ago:
                                recent_count += 1
                                
                    except Exception:
                        continue
                
                if len(qa_keys) > 0:
                    stats['average_rating'] = total_rating / len(qa_keys)
                    stats['total_usage'] = total_usage
                    stats['popular_tags'] = dict(sorted(tag_counts.items(), 
                                                      key=lambda x: x[1], reverse=True)[:10])
                    stats['recent_additions'] = recent_count
            
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return {}
    
    def cleanup_old_entries(self, days_threshold: int = 90, min_rating: float = 2.0):
        """Очищает старые записи с низким рейтингом"""
        try:
            if not self.redis_client:
                return
            
            cutoff_date = datetime.now() - timedelta(days=days_threshold)
            qa_keys = self.redis_client.keys("qa:*")
            deleted_count = 0
            
            for key in qa_keys:
                try:
                    data = self.redis_client.get(key)
                    if data:
                        qa_entry = QAEntry.from_dict(json.loads(data))
                        created_date = datetime.fromisoformat(qa_entry.created_at)
                        
                        # Удаляем старые записи с низким рейтингом и малым использованием
                        if (created_date < cutoff_date and 
                            qa_entry.rating < min_rating and 
                            qa_entry.usage_count < 5):
                            
                            # Удаляем из Redis
                            self.redis_client.delete(key)
                            
                            # Удаляем из векторной базы
                            if self.vector_store:
                                self.vector_store.delete(ids=[qa_entry.id])
                            
                            deleted_count += 1
                            
                except Exception:
                    continue
            
            logger.info(f"Очистка завершена: удалено {deleted_count} записей")
            
        except Exception as e:
            logger.error(f"Ошибка при очистке старых записей: {e}")