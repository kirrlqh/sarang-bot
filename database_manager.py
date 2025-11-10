from config import supabase, ADMIN_ID


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
    def update_admin_info(user_id, username="", full_name=""):
        """Обновить информацию об администраторе"""
        try:
            response = supabase.table("admins").update({
                "username": username,
                "full_name": full_name
            }).eq("user_id", user_id).execute()

            print(f"✅ Информация администратора {user_id} обновлена")
            return True
        except Exception as e:
            print(f"❌ Ошибка при обновлении информации администратора: {e}")
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