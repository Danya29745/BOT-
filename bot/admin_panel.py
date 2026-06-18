"""
Админ-панель для управления ботом и аналитики
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .config import ADMIN_CHAT_ID
from .analytics import BotAnalytics
from .user_manager import UserManager

logger = logging.getLogger(__name__)

class AdminPanel:
    """Класс для админ-панели бота"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.analytics = BotAnalytics(redis_client) if redis_client else None
        self.user_manager = UserManager(redis_client) if redis_client else None
        self.admin_chat_id = ADMIN_CHAT_ID
    
    def is_admin(self, user_id: str) -> bool:
        """Проверяет, является ли пользователь администратором"""
        return str(user_id) == str(self.admin_chat_id)
    
    def get_admin_menu(self) -> InlineKeyboardMarkup:
        """Возвращает главное меню админ-панели"""
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats'),
             InlineKeyboardButton("👥 Пользователи", callback_data='admin_users')],
            [InlineKeyboardButton("📄 Документы", callback_data='admin_documents'),
             InlineKeyboardButton("💬 Обратная связь", callback_data='admin_feedback')],
            [InlineKeyboardButton("🤖 Токены ИИ", callback_data='admin_tokens'),
             InlineKeyboardButton("⚙️ Настройки бота", callback_data='admin_settings')],
            [InlineKeyboardButton("🔄 Обслуживание", callback_data='admin_maintenance'),
             InlineKeyboardButton("🚨 Мониторинг", callback_data='admin_monitoring')],
            [InlineKeyboardButton("📈 Детальная аналитика", callback_data='admin_detailed_stats')],
            [InlineKeyboardButton("❌ Закрыть панель", callback_data='admin_close')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_stats_menu(self) -> InlineKeyboardMarkup:
        """Меню статистики"""
        keyboard = [
            [InlineKeyboardButton("📅 За сегодня", callback_data='admin_stats_today'),
             InlineKeyboardButton("📅 За неделю", callback_data='admin_stats_week')],
            [InlineKeyboardButton("📅 За месяц", callback_data='admin_stats_month'),
             InlineKeyboardButton("📊 Общая статистика", callback_data='admin_stats_total')],
            [InlineKeyboardButton("⭐ Рейтинги", callback_data='admin_stats_ratings'),
             InlineKeyboardButton("🔥 Популярные вопросы", callback_data='admin_stats_popular')],
            [InlineKeyboardButton("🔙 Назад", callback_data='admin_main')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_users_menu(self) -> InlineKeyboardMarkup:
        """Меню управления пользователями"""
        keyboard = [
            [InlineKeyboardButton("👥 Активные пользователи", callback_data='admin_users_active'),
             InlineKeyboardButton("📈 Новые пользователи", callback_data='admin_users_new')],
            [InlineKeyboardButton("🚫 Заблокированные", callback_data='admin_users_blocked'),
             InlineKeyboardButton("⭐ Топ пользователи", callback_data='admin_users_top')],
            [InlineKeyboardButton("🔍 Поиск пользователя", callback_data='admin_users_search'),
             InlineKeyboardButton("📊 Статистика по пользователям", callback_data='admin_users_stats')],
            [InlineKeyboardButton("🔙 Назад", callback_data='admin_main')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_documents_menu(self) -> InlineKeyboardMarkup:
        """Меню управления документами"""
        keyboard = [
            [InlineKeyboardButton("📚 Статус документов", callback_data='admin_docs_status'),
             InlineKeyboardButton("🔄 Перезагрузить", callback_data='admin_docs_reload')],
            [InlineKeyboardButton("📤 Загрузить документ", callback_data='admin_docs_upload'),
             InlineKeyboardButton("🗑️ Удалить документ", callback_data='admin_docs_delete')],
            [InlineKeyboardButton("📋 Список документов", callback_data='admin_docs_list'),
             InlineKeyboardButton("🔍 Поиск в документах", callback_data='admin_docs_search')],
            [InlineKeyboardButton("🔙 Назад", callback_data='admin_main')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def get_system_stats(self) -> Dict:
        """Получает системную статистику"""
        stats = {
            'timestamp': datetime.now().isoformat(),
            'redis_status': 'unknown',
            'total_users': 0,
            'active_users_today': 0,
            'total_questions': 0,
            'total_documents_checked': 0,
            'average_rating': 0.0,
            'error_rate': 0.0,
            'tokens_today': {},
            'tokens_total': {},
            'token_cost_today': {}
        }
        
        if not self.redis_client:
            return stats
        
        try:
            # Проверяем Redis
            self.redis_client.ping()
            stats['redis_status'] = 'connected'
            
            # Получаем статистику за сегодня
            today = datetime.now().strftime("%Y-%m-%d")
            daily_stats = self.analytics.get_daily_stats(today) if self.analytics else {}
            
            stats.update({
                'total_questions': daily_stats.get('ask_question', 0),
                'total_documents_checked': daily_stats.get('check_document', 0),
                'total_actions': daily_stats.get('total_actions', 0)
            })
            
            # Средний рейтинг
            if self.analytics:
                stats['average_rating'] = self.analytics.get_average_rating()
                
                # Статистика токенов
                stats['tokens_today'] = self.analytics.get_token_stats('today')
                stats['tokens_total'] = self.analytics.get_token_stats('total')
                stats['token_cost_today'] = self.analytics.get_token_cost_stats('today')
            
            # Количество пользователей (приблизительно)
            user_keys = self.redis_client.keys("user_stats:*")
            stats['total_users'] = len(user_keys)
            
            # Активные пользователи за сегодня
            active_keys = self.redis_client.keys(f"analytics:user:*:{today}*")
            unique_users = set()
            for key in active_keys[:100]:  # Ограничиваем для производительности
                if isinstance(key, bytes):
                    key = key.decode()
                parts = key.split(':')
                if len(parts) >= 3:
                    unique_users.add(parts[2])
            stats['active_users_today'] = len(unique_users)
            
        except Exception as e:
            logger.error(f"Ошибка при получении системной статистики: {e}")
            stats['redis_status'] = 'error'
        
        return stats
    
    async def get_feedback_summary(self) -> Dict:
        """Получает сводку по обратной связи"""
        summary = {
            'bug_reports': 0,
            'suggestions': 0,
            'low_ratings': 0,
            'recent_feedback': []
        }
        
        if not self.redis_client:
            return summary
        
        try:
            # Отчеты об ошибках
            bug_keys = self.redis_client.keys("feedback:bug:*")
            summary['bug_reports'] = len(bug_keys)
            
            # Предложения
            suggestion_keys = self.redis_client.keys("feedback:suggestion:*")
            summary['suggestions'] = len(suggestion_keys)
            
            # Низкие оценки (за последние 7 дней)
            week_ago = datetime.now() - timedelta(days=7)
            rating_keys = self.redis_client.keys("ratings:*")
            low_ratings = 0
            
            for key in rating_keys[:50]:  # Ограничиваем для производительности
                try:
                    data = self.redis_client.get(key)
                    if data:
                        rating_data = json.loads(data)
                        rating_date = datetime.fromisoformat(rating_data['timestamp'])
                        if rating_date >= week_ago and rating_data['rating'] <= 2:
                            low_ratings += 1
                except Exception:
                    continue
            
            summary['low_ratings'] = low_ratings
            
            # Последние отзывы
            recent_keys = sorted(bug_keys + suggestion_keys, reverse=True)[:5]
            for key in recent_keys:
                try:
                    data = self.redis_client.get(key)
                    if data:
                        feedback_data = json.loads(data)
                        summary['recent_feedback'].append({
                            'type': feedback_data.get('type', 'unknown'),
                            'timestamp': feedback_data.get('timestamp', ''),
                            'user_id': feedback_data.get('user_id', ''),
                            'content': feedback_data.get('report', feedback_data.get('suggestion', ''))[:100]
                        })
                except Exception:
                    continue
            
        except Exception as e:
            logger.error(f"Ошибка при получении сводки обратной связи: {e}")
        
        return summary
    
    def format_stats_message(self, stats: Dict, period: str = "сегодня") -> str:
        """Форматирует сообщение со статистикой"""
        message = f"📊 **СТАТИСТИКА ЗА {period.upper()}**\n\n"
        
        message += f"🕐 **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        message += f"🔴 **Redis:** {stats.get('redis_status', 'unknown')}\n\n"
        
        message += "👥 **ПОЛЬЗОВАТЕЛИ:**\n"
        message += f"• Всего пользователей: **{stats.get('total_users', 0)}**\n"
        message += f"• Активных сегодня: **{stats.get('active_users_today', 0)}**\n\n"
        
        message += "📈 **АКТИВНОСТЬ:**\n"
        message += f"• Всего действий: **{stats.get('total_actions', 0)}**\n"
        message += f"• Задано вопросов: **{stats.get('total_questions', 0)}**\n"
        message += f"• Проверено документов: **{stats.get('total_documents_checked', 0)}**\n\n"
        
        # Добавляем статистику токенов
        tokens_today = stats.get('tokens_today', {})
        tokens_total = stats.get('tokens_total', {})
        token_cost = stats.get('token_cost_today', {})
        
        if tokens_today or tokens_total:
            message += "🤖 **ИСПОЛЬЗОВАНИЕ ИИ:**\n"
            
            if period == "сегодня" and tokens_today:
                message += f"• Токенов сегодня: **{tokens_today.get('total_tokens', 0):,}**\n"
                message += f"  - Входящих: {tokens_today.get('prompt_tokens', 0):,}\n"
                message += f"  - Исходящих: {tokens_today.get('completion_tokens', 0):,}\n"
                message += f"• Запросов к ИИ: **{tokens_today.get('requests_count', 0)}**\n"
                
                if token_cost.get('total_cost_usd', 0) > 0:
                    message += f"• Стоимость сегодня: **${token_cost['total_cost_usd']:.4f}**\n"
                    message += f"• Средняя стоимость запроса: **${token_cost['avg_cost_per_request']:.4f}**\n"
            
            elif tokens_total:
                message += f"• Всего токенов: **{tokens_total.get('total_tokens', 0):,}**\n"
                message += f"• Всего запросов к ИИ: **{tokens_total.get('requests_count', 0)}**\n"
                
                if tokens_total.get('total_tokens', 0) > 0:
                    total_cost = self.analytics.calculate_token_cost(
                        tokens_total.get('prompt_tokens', 0),
                        tokens_total.get('completion_tokens', 0)
                    ) if self.analytics else 0
                    message += f"• Общая стоимость: **${total_cost:.4f}**\n"
            
            message += "\n"
        
        message += "⭐ **КАЧЕСТВО:**\n"
        message += f"• Средний рейтинг: **{stats.get('average_rating', 0):.1f}/5.0**\n"
        message += f"• Уровень ошибок: **{stats.get('error_rate', 0):.1f}%**\n"
        
        return message
    
    def format_feedback_message(self, feedback: Dict) -> str:
        """Форматирует сообщение с обратной связью"""
        message = "💬 **ОБРАТНАЯ СВЯЗЬ**\n\n"
        
        message += "📊 **СВОДКА:**\n"
        message += f"• Отчеты об ошибках: **{feedback.get('bug_reports', 0)}**\n"
        message += f"• Предложения: **{feedback.get('suggestions', 0)}**\n"
        message += f"• Низкие оценки (неделя): **{feedback.get('low_ratings', 0)}**\n\n"
        
        recent = feedback.get('recent_feedback', [])
        if recent:
            message += "🕐 **ПОСЛЕДНИЕ ОТЗЫВЫ:**\n"
            for item in recent[:3]:
                type_emoji = "🐛" if item['type'] == 'bug_report' else "💡"
                timestamp = item['timestamp'][:10] if item['timestamp'] else 'N/A'
                message += f"{type_emoji} {timestamp} | ID: {item['user_id']}\n"
                message += f"   _{item['content'][:80]}..._\n\n"
        
        return message

    async def handle_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /admin"""
        user_id = str(update.effective_user.id)
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return
        
        welcome_message = """
🔧 **АДМИН-ПАНЕЛЬ NEURALEX**

Добро пожаловать в панель управления ботом!

📊 Здесь вы можете:
• Просматривать статистику и аналитику
• Управлять пользователями
• Загружать и управлять документами
• Просматривать обратную связь
• Настраивать параметры бота
• Выполнять техническое обслуживание

Выберите нужный раздел:
        """
        
        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown',
            reply_markup=self.get_admin_menu()
        )