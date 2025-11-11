import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Уменьшаем логирование HTTP запросов
logging.getLogger("httpx").setLevel(logging.WARNING)

# Импорты
try:
    from config import ADMIN_ID, BOT_TOKEN, supabase
    from database_manager import DatabaseManager
except ImportError as e:
    logger.error(f"Import error: {e}")
    exit(1)

# Проверка подключения к Supabase
if supabase is None:
    logger.error("❌ Критическая ошибка: Не удалось подключиться к Supabase")
    exit(1)


# Главное меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Не указан"
    full_name = f"{update.message.from_user.first_name or ''} {update.message.from_user.last_name or ''}".strip()

    # Автоматически обновляем информацию об администраторах
    if DatabaseManager.is_admin(user_id):
        DatabaseManager.update_admin_info(user_id, username, full_name)
        logger.info(f"✅ Обновлены данные админа: {user_id} - {full_name} (@{username})")

    keyboard = [
        [InlineKeyboardButton("🍽 Меню", callback_data='menu')],
        [InlineKeyboardButton("📋 Лист", callback_data='sheet')],
        [InlineKeyboardButton("📅 График", callback_data='schedule')],
        [InlineKeyboardButton("🪑 Посадка", callback_data='seating')],
        [InlineKeyboardButton("📝 Обратная связь", callback_data='feedback')]  # Новая кнопка
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text('Выберите опцию:', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text('Выберите опцию:', reply_markup=reply_markup)

# Обработчик нажатий на кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Главное меню
    if data == 'menu':
        await show_categories(query)
    elif data == 'sheet':
        await show_sheet_options(query)
    elif data == 'schedule':
        await show_schedule_options(query)
    elif data == 'seating':
        await show_seating(query)

    # Категории меню
    elif data.startswith('category_'):
        category_id = int(data.split('_')[1])
        await show_dishes(query, category_id)

    # Просмотр блюда
    elif data.startswith('dish_'):
        dish_id = int(data.split('_')[1])
        await show_dish_detail(query, dish_id)

    # Лист
    elif data == 'view_go':
        await view_sheet(query, 'go')
    elif data == 'view_start':
        await view_sheet(query, 'start')
    elif data == 'update_sheet':
        if not DatabaseManager.is_admin(query.from_user.id):
            await query.edit_message_text(text="❌ У вас нет прав для обновления листа.")
            return
        await choose_sheet_type(query)

    elif data in ['set_go', 'set_start']:
        sheet_type = 'go' if data == 'set_go' else 'start'
        context.user_data['waiting_for_sheet_update'] = sheet_type
        await query.edit_message_text(text=f"Введите новый текст для {sheet_type} листа:")

    # График
    elif data == 'view_schedule':
        await send_schedule_photo(query)
    elif data == 'update_schedule':
        if not DatabaseManager.is_admin(query.from_user.id):
            await query.edit_message_text(text="❌ У вас нет прав для обновления графика.")
            return
        context.user_data['waiting_for_schedule'] = True
        await query.edit_message_text(text="Отправьте новое фото графика:")

    # Обратная связь - выбор стола
    elif data.startswith('feedback_table_'):
        table_number = int(data.split('_')[2])
        context.user_data['feedback_table'] = table_number
        context.user_data['waiting_for_feedback'] = True

        await query.edit_message_text(
            f"🪑 Выбран стол {table_number}\n\n"
            f"Напишите ваш комментарий:"
        )

    # Отмена обратной связи
    elif data == 'feedback_cancel':
        if 'waiting_for_feedback' in context.user_data:
            del context.user_data['waiting_for_feedback']
        await query.edit_message_text("❌ Отзыв отменен")

    # Кнопка обратной связи из главного меню
    elif data == 'feedback':
        # Используем query.message для ответа на callback
        context.user_data['feedback_user'] = {
            'user_id': query.from_user.id,
            'username': query.from_user.username or "Не указан",
            'full_name': f"{query.from_user.first_name or ''} {query.from_user.last_name or ''}".strip()
        }

        # Автоматическая очистка старых отзывов
        DatabaseManager.auto_cleanup_feedback()

        # Создаем клавиатуру с номерами столов (1-37)
        keyboard = []
        row = []
        for i in range(1, 38):  # Столы с 1 по 37
            row.append(InlineKeyboardButton(f"Стол {i}", callback_data=f"feedback_table_{i}"))
            if i % 4 == 0:  # 4 кнопки в ряд
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='feedback_cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "📝 Обратная связь\n\n"
            "Выберите номер стола:",
            reply_markup=reply_markup
        )
    # Возврат в главное меню
    elif data == 'back_main':
        await start(update, context)
    elif data == 'back_categories':
        await show_categories(query)


# --- ФУНКЦИИ ДЛЯ МЕНЮ ---
async def show_categories(query):
    categories = DatabaseManager.get_categories()
    if not categories:
        await query.edit_message_text(text="❌ Категории не найдены в базе данных")
        return

    keyboard = []
    for category in categories:
        keyboard.append([InlineKeyboardButton(
            category['name'],
            callback_data=f"category_{category['id']}"
        )])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back_main')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Выберите категорию:", reply_markup=reply_markup)


async def show_dishes(query, category_id):
    dishes = DatabaseManager.get_dishes_by_category(category_id)
    keyboard = []

    for dish in dishes:
        display_name = dish['name'][:30] + "..." if len(dish['name']) > 30 else dish['name']
        keyboard.append([InlineKeyboardButton(
            display_name,
            callback_data=f"dish_{dish['id']}"
        )])

    # Получаем название категории для заголовка
    categories = DatabaseManager.get_categories()
    category_name = next((cat['name'] for cat in categories if cat['id'] == category_id), "Категория")

    keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if dishes:
        await query.edit_message_text(text=f"Блюда в категории '{category_name}':", reply_markup=reply_markup)
    else:
        await query.edit_message_text(text=f"В категории '{category_name}' пока нет блюд.", reply_markup=reply_markup)


async def show_dish_detail(query, dish_id):
    dish = DatabaseManager.get_dish(dish_id)

    if dish:
        text = f"<b>{dish['name']}</b>\n\n"

        if dish.get('composition'):
            text += f"<i>Состав:</i>\n{dish['composition']}\n\n"

        if dish.get('description'):
            text += f"<i>Описание:</i>\n{dish['description']}\n\n"

        if dish.get('price'):
            text += f"<i>Цена:</i> {dish['price']} руб."
        else:
            text += "<i>Цена:</i> Не указана"

        # Кнопка назад
        keyboard = [[InlineKeyboardButton(
            "⬅️ Назад к блюдам",
            callback_data=f"category_{dish['category_id']}"
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Если есть фото, отправляем его с подписью
        if dish.get('photo_file_id'):
            try:
                await query.message.reply_photo(
                    photo=dish['photo_file_id'],
                    caption=text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                return
            except Exception as e:
                logger.error(f"Error sending photo: {e}")
                # Если фото не загружено, продолжаем без него

        # Если фото нет или ошибка при отправке фото
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text(text="Блюдо не найдено.")


# --- ФУНКЦИИ ДЛЯ ЛИСТА ---
async def show_sheet_options(query):
    keyboard = [
        [InlineKeyboardButton("👁‍🗨 Go Лист", callback_data='view_go')],
        [InlineKeyboardButton("👁‍🗨 Start Лист", callback_data='view_start')],
        [InlineKeyboardButton("✏️ Обновить лист", callback_data='update_sheet')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Выберите опцию для листа:", reply_markup=reply_markup)


async def view_sheet(query, sheet_type):
    sheet = DatabaseManager.get_sheet(sheet_type)
    if sheet:
        sheet_name = "Go Лист" if sheet_type == 'go' else "Start Лист"
        text = f"<b>{sheet_name}:</b>\n\n{sheet['content']}"

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='sheet')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await query.edit_message_text(text="Лист не найден.")


async def choose_sheet_type(query):
    keyboard = [
        [InlineKeyboardButton("Go Лист", callback_data='set_go')],
        [InlineKeyboardButton("Start Лист", callback_data='set_start')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='sheet')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Какой лист обновляем?", reply_markup=reply_markup)


# --- ФУНКЦИИ ДЛЯ ГРАФИКА ---
async def show_schedule_options(query):
    keyboard = [
        [InlineKeyboardButton("👁‍🗨 Посмотреть график", callback_data='view_schedule')],
        [InlineKeyboardButton("✏️ Обновить график", callback_data='update_schedule')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Выберите опцию для графика:", reply_markup=reply_markup)


async def send_schedule_photo(query):
    file_data = DatabaseManager.get_file('schedule')

    # Проверяем, что file_data существует и file_id не пустой
    if file_data and file_data.get('file_id') and file_data['file_id'].strip():
        try:
            # Отправляем фото как новое сообщение
            await query.message.reply_photo(
                photo=file_data['file_id'],
                caption="📅 График работы\n\n⬅️ Используйте кнопку 'Назад' в основном меню",
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке фото графика: {e}")
            await query.message.reply_text(
                text="❌ Ошибка при загрузке графика. Попробуйте обновить его."
            )
    else:
        await query.edit_message_text(text="📅 График еще не загружен.")


# --- ФУНКЦИИ ДЛЯ ПОСАДКИ ---
async def show_seating(query):
    file_data = DatabaseManager.get_file('seating')

    # Проверяем, что file_data существует и file_id не пустой
    if file_data and file_data.get('file_id') and file_data['file_id'].strip():
        try:
            # Отправляем фото как новое сообщение
            await query.message.reply_photo(
                photo=file_data['file_id'],
                caption="🪑 Схема посадки\n\n⬅️ Используйте кнопку 'Назад' в основном меню",
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке фото посадки: {e}")
            await query.message.reply_text(
                text="❌ Ошибка при загрузке схемы посадки. Попробуйте обновить её."
            )
    else:
        await query.edit_message_text(text="🪑 Схема посадки еще не загружена.")


# --- КОМАНДЫ ДЛЯ АДМИНИСТРИРОВАНИЯ ---
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить администратора с автоматическим получением данных"""
    user_id = update.message.from_user.id

    # Проверяем, что текущий пользователь - админ
    if not DatabaseManager.is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    # Проверяем, передан ли user_id аргументом
    if not context.args:
        await update.message.reply_text(
            "ℹ️ Использование: /add_admin <user_id>\n\n"
            "Чтобы узнать user_id пользователя, попросите его написать @userinfobot"
        )
        return

    try:
        new_admin_id = int(context.args[0])

        # Пытаемся получить информацию о пользователе через Telegram API
        try:
            bot = context.bot
            user = await bot.get_chat(new_admin_id)

            username = user.username or "Не указан"
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if not full_name:
                full_name = "Не указано"

            user_info = f"👤 Имя: {full_name}\n📱 Username: @{username}"

        except Exception as e:
            # Если не удалось получить данные (пользователь не писал боту или скрыт)
            logger.warning(f"Не удалось получить данные пользователя {new_admin_id}: {e}")
            username = "Не указан"
            full_name = "Не указано"
            user_info = "⚠️ Не удалось получить данные пользователя. Они обновятся когда пользователь напишет боту."

        # Проверяем, не является ли пользователь уже админом
        if DatabaseManager.is_admin(new_admin_id):
            await update.message.reply_text("❌ Этот пользователь уже является администратором.")
            return

        # Добавляем в базу
        success = DatabaseManager.add_admin(new_admin_id, username, full_name)

        if success:
            await update.message.reply_text(
                f"✅ Администратор успешно добавлен!\n\n"
                f"🆔 ID: {new_admin_id}\n"
                f"{user_info}"
            )
        else:
            await update.message.reply_text("❌ Ошибка при добавлении администратора в базу данных.")

    except ValueError:
        await update.message.reply_text("❌ Неверный формат user_id. user_id должен быть числом.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении админа: {e}")
        await update.message.reply_text("❌ Произошла ошибка при добавлении администратора.")


async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список администраторов с актуальными данными"""
    user_id = update.message.from_user.id

    if not DatabaseManager.is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    admins = DatabaseManager.get_all_admins()

    if not admins:
        await update.message.reply_text("📋 Список администраторов пуст.")
        return

    admin_list = "📋 Список администраторов:\n\n"
    for i, admin in enumerate(admins, 1):
        admin_list += f"{i}. 🆔 ID: {admin['user_id']}\n"
        admin_list += f"   👤 Имя: {admin.get('full_name', 'Не указано')}\n"
        admin_list += f"   📱 Username: @{admin.get('username', 'Не указан')}\n"

        # Показываем когда обновлялись данные
        if admin.get('created_at'):
            created = admin['created_at'][:10]  # Берем только дату
            admin_list += f"   📅 Добавлен: {created}\n"

        admin_list += "   " + "─" * 25 + "\n"

    await update.message.reply_text(admin_list)


async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить администратора"""
    user_id = update.message.from_user.id

    if not DatabaseManager.is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    if not context.args:
        await update.message.reply_text(
            "ℹ️ Использование: /remove_admin <user_id>"
        )
        return

    try:
        remove_admin_id = int(context.args[0])

        # Не позволяем удалить самого себя
        if remove_admin_id == user_id:
            await update.message.reply_text("❌ Вы не можете удалить сами себя.")
            return

        success = DatabaseManager.remove_admin(remove_admin_id)

        if success:
            await update.message.reply_text(f"✅ Пользователь {remove_admin_id} удален из администраторов!")
        else:
            await update.message.reply_text("❌ Ошибка при удалении администратора.")

    except ValueError:
        await update.message.reply_text("❌ Неверный формат user_id.")
    except Exception as e:
        logger.error(f"Ошибка при удалении админа: {e}")
        await update.message.reply_text("❌ Произошла ошибка при удалении администратора.")


# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # Обработка комментария для обратной связи
    if context.user_data.get('waiting_for_feedback'):
        table_number = context.user_data.get('feedback_table')
        user_data = context.user_data.get('feedback_user', {})

        if table_number and user_data and text.strip():
            success = DatabaseManager.add_feedback(
                table_number=table_number,
                user_id=user_data['user_id'],
                username=user_data['username'],
                full_name=user_data['full_name'],
                comment=text.strip()
            )

            # Очищаем контекст
            del context.user_data['waiting_for_feedback']
            del context.user_data['feedback_table']
            del context.user_data['feedback_user']

            if success:
                await update.message.reply_text(
                    f"✅ Спасибо за отзыв!\n\n"
                    f"🪑 Стол {table_number}\n"
                    f"💬 Ваш комментарий учтен"
                )
            else:
                await update.message.reply_text("❌ Ошибка при сохранении отзыва")
        return

    if context.user_data.get('waiting_for_sheet_update'):
        sheet_type = context.user_data['waiting_for_sheet_update']
        success = DatabaseManager.update_sheet(sheet_type, text, user_id)

        del context.user_data['waiting_for_sheet_update']

        if success:
            sheet_name = "Go" if sheet_type == 'go' else "Start"
            await update.message.reply_text(f"✅ {sheet_name} лист обновлен!")
            await start(update, context)
        else:
            await update.message.reply_text("❌ Ошибка при обновлении листа.")
        return


async def feedback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс оставления отзыва"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Не указан"
    full_name = f"{update.message.from_user.first_name or ''} {update.message.from_user.last_name or ''}".strip()

    # Сохраняем данные пользователя в контекст
    context.user_data['feedback_user'] = {
        'user_id': user_id,
        'username': username,
        'full_name': full_name
    }

    # Автоматическая очистка старых отзывов
    deleted_count = DatabaseManager.auto_cleanup_feedback()
    if deleted_count > 0:
        logger.info(f"🔄 Автоматически удалено {deleted_count} старых отзывов")

    # Создаем клавиатуру с номерами столов (1-37)
    keyboard = []
    row = []
    for i in range(1, 38):  # Столы с 1 по 37
        row.append(InlineKeyboardButton(f"Стол {i}", callback_data=f"feedback_table_{i}"))
        if i % 4 == 0:  # 4 кнопки в ряд
            keyboard.append(row)
            row = []

    # Добавляем последний ряд если нужно
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='feedback_cancel')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📝 Обратная связь\n\n"
        "Выберите номер стола:",
        reply_markup=reply_markup
    )


async def view_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все отзывы (только для админов)"""
        user_id = update.message.from_user.id

        if not DatabaseManager.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return

        # Автоматическая очистка перед показом
        deleted_count = DatabaseManager.auto_cleanup_feedback()

        feedback_list = DatabaseManager.get_all_feedback()

        if not feedback_list:
            if deleted_count > 0:
                await update.message.reply_text(f"📝 Отзывов нет. Удалено {deleted_count} старых отзывов.")
            else:
                await update.message.reply_text("📝 Отзывов пока нет.")
            return

        feedback_text = f"📝 Все отзывы (удалено {deleted_count} старых):\n\n"

        for feedback in feedback_list:
            created_at = feedback.get('created_at', '')[:16]  # Берем дату и время
            table_number = feedback['table_number']
            comment = feedback['comment']
            full_name = feedback.get('full_name', 'Неизвестно')
            username = feedback.get('username', 'Не указан')

            feedback_text += f"🪑 Стол {table_number}\n"
            feedback_text += f"👤 {full_name} (@{username})\n"
            feedback_text += f"📅 {created_at}\n"
            feedback_text += f"💬 {comment}\n"
            feedback_text += "─" * 30 + "\n"

        await update.message.reply_text(feedback_text)

# Обработка фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    photo = update.message.photo[-1]
    file_id = photo.file_id

    logger.info(f"🖼 Получено фото от пользователя {user_id}")

    if context.user_data.get('waiting_for_schedule'):
        logger.info("🔄 Обновление графика...")
        if DatabaseManager.is_admin(user_id):
            success = DatabaseManager.update_file('schedule', file_id, user_id, 'График')
            del context.user_data['waiting_for_schedule']
            if success:
                logger.info("✅ График успешно обновлен в базе данных")
                await update.message.reply_text("✅ График обновлен!")
                await start(update, context)
            else:
                logger.error("❌ Ошибка при обновлении графика в базе данных")
                await update.message.reply_text("❌ Ошибка при обновлении графика.")
        else:
            logger.warning("❌ Пользователь не является администратором")
            await update.message.reply_text("❌ У вас нет прав для обновления графика.")
    else:
        # Обновление схемы посадки (только для админов)
        logger.info("🔄 Обновление схемы посадки...")
        if DatabaseManager.is_admin(user_id):
            success = DatabaseManager.update_file('seating', file_id, user_id, 'Схема посадки')
            if success:
                logger.info("✅ Схема посадки успешно обновлена в базе данных")
                await update.message.reply_text("✅ Схема посадки обновлена!")
            else:
                logger.error("❌ Ошибка при обновлении схемы посадки в базе данных")
                await update.message.reply_text("❌ Ошибка при обновлении схемы посадки.")
        else:
            logger.info("ℹ️ Пользователь отправил фото, но не является админом")
            await update.message.reply_text("ℹ️ Фото получено. Для обновления графиков обратитесь к администратору.")


def main():
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        # Команды и обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("add_admin", add_admin))
        application.add_handler(CommandHandler("list_admins", list_admins))
        application.add_handler(CommandHandler("remove_admin", remove_admin))
        application.add_handler(CommandHandler("view_feedback", view_feedback))  # Команда для просмотра отзывов
        application.add_handler(CallbackQueryHandler(button))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

        # Автоматическая очистка при запуске
        deleted_count = DatabaseManager.auto_cleanup_feedback()
        if deleted_count > 0:
            print(f"🔄 При запуске удалено {deleted_count} старых отзывов")

        # Запуск бота
        logger.info("🤖 Бот запускается на Railway...")
        print("🚀 Restaurant Bot запущен на Railway!")
        print("📊 Мониторинг: https://railway.app")
        print("👑 Команды администратора:")
        print("   /add_admin <user_id> - Добавить администратора")
        print("   /list_admins - Показать список администраторов")
        print("   /remove_admin <user_id> - Удалить администратора")
        print("   /view_feedback - Показать все отзывы")
        print("📝 Команды пользователя:")
        print("   Нажмите 'Обратная связь' в меню")

        application.run_polling()

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    main()