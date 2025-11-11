from config import supabase, ADMIN_ID
import threading
import time
from datetime import datetime, timedelta
import pytz


class DatabaseManager:

    @staticmethod
    def get_categories():
        """Получить все категории"""
        try:
            response = supabase.table("categories").select("*").order("sort_order").execute()
            return response.data
        except Exception as e:
            print(f"Error getting categories: {e}")
            return []

    @staticmethod
    def get_dishes_by_category(category_id):
        """Получить блюда по категории"""
        try:
            response = (supabase.table("dishes")
                        .select("*")
                        .eq("category_id", category_id)
                        .eq("is_available", True)
                        .order("sort_order")
                        .execute())
            return response.data
        except Exception as e:
            print(f"Error getting dishes: {e}")
            return []

    @staticmethod
    def get_dish(dish_id):
        """Получить блюдо по ID"""
        try:
            response = supabase.table("dishes").select("*").eq("id", dish_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting dish: {e}")
            return None

    @staticmethod
    def get_sheet(sheet_type):
        try:
            response = supabase.table("sheets").select("*").eq("sheet_type", sheet_type).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting sheet: {e}")
            return None

    @staticmethod
    def update_sheet(sheet_type, content, user_id):
        try:
            response = (supabase.table("sheets")
                        .update({"content": content, "updated_by": user_id})
                        .eq("sheet_type", sheet_type)
                        .execute())
            return True
        except Exception as e:
            print(f"Error updating sheet: {e}")
            return False

    @staticmethod
    def get_file(file_type):
        try:
            response = supabase.table("files").select("*").eq("file_type", file_type).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting file: {e}")
            return None

    @staticmethod
    def update_file(file_type, file_id, user_id, file_name=""):
        try:
            print(f"🔄 Обновление файла в базе: type={file_type}, file_id={file_id[:20]}..., user={user_id}")

            # Проверяем, что file_id не пустой
            if not file_id or not file_id.strip():
                print("❌ Пустой file_id")
                return False

            # Сначала проверяем, существует ли запись
            existing = supabase.table("files").select("*").eq("file_type", file_type).execute()

            if existing.data:
                # Обновляем существующую запись
                response = (supabase.table("files")
                            .update({
                    "file_id": file_id,
                    "updated_by": user_id,
                    "file_name": file_name
                })
                            .eq("file_type", file_type)
                            .execute())
            else:
                # Создаем новую запись
                response = (supabase.table("files")
                            .insert({
                    "file_type": file_type,
                    "file_id": file_id,
                    "updated_by": user_id,
                    "file_name": file_name
                })
                            .execute())

            print(f"✅ Файл успешно обновлен/добавлен")
            return True
        except Exception as e:
            print(f"❌ Критическая ошибка при обновлении файла {file_type}: {e}")
            return False

    @staticmethod
    def is_admin(user_id):
        try:
            response = supabase.table("admins").select("*").eq("user_id", user_id).execute()
            return len(response.data) > 0
        except Exception as e:
            print(f"Error checking admin: {e}")
            # Если таблицы admins нет, проверяем по ADMIN_ID из config
            return user_id == ADMIN_ID

    @staticmethod
    def add_admin(user_id, username="", full_name=""):
        """Добавить администратора"""
        try:
            response = supabase.table("admins").insert({
                "user_id": user_id,
                "username": username,
                "full_name": full_name
            }).execute()

            print(f"✅ Администратор {user_id} добавлен в базу")
            return True
        except Exception as e:
            print(f"❌ Ошибка при добавлении администратора: {e}")
            return False

    @staticmethod
    def remove_admin(user_id):
        """Удалить администратора"""
        try:
            response = supabase.table("admins").delete().eq("user_id", user_id).execute()
            print(f"✅ Администратор {user_id} удален из базы")
            return True
        except Exception as e:
            print(f"❌ Ошибка при удалении администратора: {e}")
            return False

    @staticmethod
    def get_all_admins():
        """Получить всех администраторов"""
        try:
            response = supabase.table("admins").select("*").execute()
            return response.data
        except Exception as e:
            print(f"❌ Ошибка при получении списка администраторов: {e}")
            return []

    # --- СИСТЕМА ОБРАТНОЙ СВЯЗИ С ВЫБОРОМ СТОЛА ---

    @staticmethod
    def add_feedback(user_id, username, full_name, message, table_number, message_type='feedback'):
        """Добавить отзыв или обратную связь с номером стола"""
        try:
            response = supabase.table("feedback").insert({
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
                "message": message,
                "table_number": table_number,
                "message_type": message_type,  # 'feedback', 'complaint', 'suggestion'
                "status": 'new'  # 'new', 'read', 'replied'
            }).execute()

            print(f"✅ Отзыв от пользователя {user_id} (стол {table_number}) добавлен в базу")
            return True
        except Exception as e:
            print(f"❌ Ошибка при добавлении отзыва: {e}")
            return False

    @staticmethod
    def get_all_feedback(status=None):
        """Получить все отзывы (для админов)"""
        try:
            query = supabase.table("feedback").select("*").order("created_at", desc=True)

            if status:
                query = query.eq("status", status)

            response = query.execute()
            return response.data
        except Exception as e:
            print(f"❌ Ошибка при получении отзывов: {e}")
            return []

    @staticmethod
    def get_feedback_stats():
        """Получить статистику по отзывам"""
        try:
            feedback = DatabaseManager.get_all_feedback()
            total = len(feedback)
            new_count = len([f for f in feedback if f.get('status') == 'new'])
            read_count = len([f for f in feedback if f.get('status') == 'read'])

            return {
                'total': total,
                'new': new_count,
                'read': read_count
            }
        except Exception as e:
            print(f"❌ Ошибка при получении статистики отзывов: {e}")
            return {'total': 0, 'new': 0, 'read': 0}

    @staticmethod
    def update_feedback_status(feedback_id, status):
        """Обновить статус отзыва"""
        try:
            response = supabase.table("feedback").update({
                "status": status
            }).eq("id", feedback_id).execute()

            return True
        except Exception as e:
            print(f"❌ Ошибка при обновлении статуса отзыва: {e}")
            return False

    @staticmethod
    def delete_feedback(feedback_id):
        """Удалить отзыв"""
        try:
            response = supabase.table("feedback").delete().eq("id", feedback_id).execute()
            print(f"✅ Отзыв {feedback_id} удален")
            return True
        except Exception as e:
            print(f"❌ Ошибка при удалении отзыва: {e}")
            return False

    @staticmethod
    def cleanup_old_feedback(days=1):
        """Очистить старые отзывы (старше указанного количества дней)"""
        try:
            # Вычисляем дату, старше которой удаляем отзывы
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            # Удаляем отзывы старше указанной даты
            response = supabase.table("feedback").delete().lt('created_at', cutoff_date).execute()

            deleted_count = len(response.data) if response.data else 0
            print(f"✅ Автоочистка: удалено {deleted_count} отзывов старше {days} дней")
            return deleted_count
        except Exception as e:
            print(f"❌ Ошибка при очистке старых отзывов: {e}")
            return 0

    @staticmethod
    def format_saratov_time(utc_time_str):
        """Форматирует время в Саратовский часовой пояс"""
        try:
            if not utc_time_str:
                return "время неизвестно"

            # Парсим UTC время из базы данных
            utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))

            # Конвертируем в Саратовское время (UTC+4)
            saratov_tz = pytz.timezone('Europe/Saratov')
            saratov_time = utc_time.astimezone(saratov_tz)

            # Форматируем в удобный вид
            return saratov_time.strftime("%d.%m.%Y %H:%M")
        except Exception as e:
            print(f"❌ Ошибка при форматировании времени: {e}")
            return utc_time_str[:16] if utc_time_str else "время неизвестно"


# --- ФОНОВАЯ ЗАДАЧА ДЛЯ ОЧИСТКИ ---

def start_cleanup_scheduler():
    """Запустить фоновую задачу для автоматической очистки"""

    def cleanup_task():
        while True:
            try:
                # Ожидаем 24 часа
                time.sleep(24 * 60 * 60)  # 24 часа в секундах

                # Выполняем очистку отзывов старше 30 дней
                DatabaseManager.cleanup_old_feedback(days=30)

            except Exception as e:
                print(f"❌ Ошибка в фоновой задаче очистки: {e}")
                time.sleep(60 * 60)  # Ждем 1 час при ошибке

    # Запускаем в отдельном потоке
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()
    print("✅ Фоновая задача автоочистки запущена")


# Запускаем очистку при импорте
start_cleanup_scheduler()