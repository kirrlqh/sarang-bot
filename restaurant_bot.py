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
    keyboard = [
        [InlineKeyboardButton("🍽 Меню", callback_data='menu')],
        [InlineKeyboardButton("📋 Лист", callback_data='sheet')],
        [InlineKeyboardButton("📅 График", callback_data='schedule')],
        [InlineKeyboardButton("🪑 Посадка", callback_data='seating')],
        [InlineKeyboardButton("💬 Обратная связь", callback_data='feedback_main')]
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
    elif data == 'feedback_main':
        await show_feedback_options(query)

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
    elif data == 'send_feedback':
        await choose_table(query, context)

    elif data.startswith('table_'):
        table_number = int(data.split('_')[1])
        context.user_data['selected_table'] = table_number
        context.user_data['waiting_for_feedback'] = True
        await query.edit_message_text(
            text=f"🪑 Выбран стол: {table_number:02d}\n\n💬 Теперь напишите ваш отзыв, предложение или жалобу:")

    elif data == 'view_feedback':
        if not DatabaseManager.is_admin(query.from_user.id):
            await query.edit_message_text(text="❌ У вас нет прав для просмотра отзывов.")
            return
        await show_feedback_list(query)

    elif data.startswith('feedback_'):
        if not DatabaseManager.is_admin(query.from_user.id):
            await query.edit_message_text(text="❌ У вас нет прав для управления отзывами.")
            return

        action, feedback_id = data.split('_')[1], data.split('_')[2]

        if action == 'view':
            await show_feedback_detail(query, int(feedback_id))
        elif action == 'markread':
            DatabaseManager.update_feedback_status(int(feedback_id), 'read')
            await query.edit_message_text(text="✅ Отзыв помечен как прочитанный")
            await show_feedback_list(query)
        elif action == 'delete':
            DatabaseManager.delete_feedback(int(feedback_id))
            await query.edit_message_text(text="✅ Отзыв удален")
            await show_feedback_list(query)

    # Возврат в главное меню
    elif data == 'back_main':
        await start(update, context)
    elif data == 'back_categories':
        await show_categories(query)
    elif data == 'back_feedback':
        await show_feedback_options(query)
    elif data == 'back_sheet':
        await show_sheet_options(query)
    elif data == 'back_schedule':
        await show_schedule_options(query)


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

    keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data='back_categories')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if dishes:
        await query.edit_message_text(text=f"Блюда в категории '{category_name}':", reply_markup=reply_markup)
    else:
        await query.edit_message_text(text=f"В категории '{category_name}' пока нет блюд.", reply_markup=reply_markup)


async def show_dish_detail(query, dish_id):
    dish = DatabaseManager.get_dish(dish_id)

    if dish:
        # Форматируем информацию о блюде
        text = f"<b>{dish['name']}</b>\n\n"

        # Время приготовления (передаем название блюда)
        cooking_time = DatabaseManager.format_cooking_time(dish.get('name'))
        text += f"{cooking_time}\n\n"

        # Острота
        spiciness = DatabaseManager.format_spiciness(dish.get('spiciness', 'Не острое'))
        if spiciness:
            text += f"<b>Острота:</b> {spiciness}\n\n"

        # Состав
        if dish.get('composition'):
            text += f"<i>🍽️ Состав:</i>\n{dish['composition']}\n\n"

        # Описание
        if dish.get('description'):
            text += f"<i>📝 Описание:</i>\n{dish['description']}\n\n"

        # Аллергены
        allergens = DatabaseManager.format_allergens(dish.get('allergens'))
        if allergens:
            text += f"<b>⚠️ Аллергены:</b>\n{allergens}\n\n"

        # Особенности
        if dish.get('features'):
            features = dish['features']
            if 'Подходит детям' in features:
                text += "👶 Подходит детям\n"
            if 'Подойдет на общий стол' in features:
                text += "👥 Подойдет на общий стол\n"
            if 'Содержит лактозу' in features:
                text += "🥛 Содержит лактозу\n"
            if 'Подается с перчатками' in features:
                text += "🧤 Подается с перчатками\n"
            if 'Подается с тарелкой теплой воды' in features:
                text += "♨️ Подается с тарелкой теплой воды\n"
            if 'Острота не регулируется' in features:
                text += "⚡ Острота не регулируется\n"
            if 'Соевый соус средней остроты' in features:
                text += "🍶 Соевый соус средней остроты\n"
            if 'Можно подогреть' in features:
                text += "🔥 Можно подогреть\n"
            if 'Можно сделать острее' in features:
                text += "🌶️ Можно сделать острее\n"
            if 'Спрашивать про рис' in features:
                text += "🍚 Спрашивать про рис\n"
            if 'Подается с доп.ингредиентами' in features:
                text += "🧂 Подается с дополнительными ингредиентами\n"

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

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_sheet')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_sheet')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Лист не найден.", reply_markup=reply_markup)


async def choose_sheet_type(query):
    keyboard = [
        [InlineKeyboardButton("Go Лист", callback_data='set_go')],
        [InlineKeyboardButton("Start Лист", callback_data='set_start')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_sheet')]
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
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_schedule')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Отправляем фото как новое сообщение
            await query.message.reply_photo(
                photo=file_data['file_id'],
                caption="📅 График работы",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке фото графика: {e}")
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_schedule')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                text="❌ Ошибка при загрузке графика. Попробуйте обновить его.",
                reply_markup=reply_markup
            )
    else:
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_schedule')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="📅 График еще не загружен.", reply_markup=reply_markup)


# --- ФУНКЦИИ ДЛЯ ПОСАДКИ ---
async def show_seating(query):
    file_data = DatabaseManager.get_file('seating')

    # Проверяем, что file_data существует и file_id не пустой
    if file_data and file_data.get('file_id') and file_data['file_id'].strip():
        try:
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_main')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Отправляем фото как новое сообщение
            await query.message.reply_photo(
                photo=file_data['file_id'],
                caption="🪑 Схема посадки",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке фото посадки: {e}")
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_main')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                text="❌ Ошибка при загрузке схемы посадки. Попробуйте обновить её.",
                reply_markup=reply_markup
            )
    else:
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="🪑 Схема посадки еще не загружена.", reply_markup=reply_markup)


# --- ФУНКЦИИ ДЛЯ ОБРАТНОЙ СВЯЗИ С ВЫБОРОМ СТОЛА ---
async def show_feedback_options(query):
    keyboard = [
        [InlineKeyboardButton("💌 Оставить отзыв", callback_data='send_feedback')],
    ]

    # Добавляем кнопку просмотра отзывов только для админов
    if DatabaseManager.is_admin(query.from_user.id):
        stats = DatabaseManager.get_feedback_stats()
        keyboard.append([InlineKeyboardButton(
            f"📊 Просмотреть отзывы ({stats['new']} новых)",
            callback_data='view_feedback'
        )])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back_main')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="💬 Обратная связь\n\nЗдесь вы можете оставить отзыв, предложение или сообщить о проблеме:",
        reply_markup=reply_markup
    )


async def choose_table(query, context):
    """Выбор стола от 1 до 37 с нормальной сеткой"""
    # Создаем сетку 5x8 для 37 столов (последний ряд будет неполным)
    tables = list(range(1, 38))

    keyboard = []
    row = []

    for i, table in enumerate(tables, 1):
        # Форматируем номер стола с ведущим нулем для красоты
        table_text = f"{table:02d}"
        row.append(InlineKeyboardButton(f"🪑 {table_text}", callback_data=f"table_{table}"))

        # Создаем новую строку каждые 5 столов
        if i % 5 == 0:
            keyboard.append(row)
            row = []

    # Добавляем последнюю неполную строку если есть
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back_feedback')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="🪑 Выберите номер вашего стола (от 1 до 37):",
        reply_markup=reply_markup
    )


async def show_feedback_list(query):
    feedback_list = DatabaseManager.get_all_feedback()
    stats = DatabaseManager.get_feedback_stats()

    if not feedback_list:
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_feedback')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="📭 Отзывов пока нет",
            reply_markup=reply_markup
        )
        return

    text = f"📊 Всего отзывов: {stats['total']} (новых: {stats['new']})\n\n"
    text += "Выберите отзыв для просмотра:\n\n"

    keyboard = []
    for feedback in feedback_list[:10]:  # Показываем последние 10 отзывов
        status_icon = "🆕" if feedback.get('status') == 'new' else "📖"
        table_number = feedback.get('table_number', '?')
        user_info = f"@{feedback.get('username', 'без username')}" if feedback.get(
            'username') else f"ID: {feedback['user_id']}"

        # Используем Саратовское время
        saratov_time = DatabaseManager.format_saratov_time(feedback.get('created_at'))

        btn_text = f"{status_icon} Стол {table_number:02d} - {saratov_time}"
        if len(btn_text) > 50:
            btn_text = btn_text[:47] + "..."

        keyboard.append([InlineKeyboardButton(
            btn_text,
            callback_data=f"feedback_view_{feedback['id']}"
        )])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back_feedback')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup)


async def show_feedback_detail(query, feedback_id):
    feedback_list = DatabaseManager.get_all_feedback()
    feedback = next((f for f in feedback_list if f['id'] == feedback_id), None)

    if not feedback:
        await query.edit_message_text(text="❌ Отзыв не найден")
        return

    status_text = {
        'new': '🆕 Новый',
        'read': '📖 Прочитан',
        'replied': '✅ Отвечен'
    }

    status = status_text.get(feedback.get('status'), '❓ Неизвестен')
    table_number = feedback.get('table_number', 'Не указан')
    user_info = f"@{feedback.get('username')}" if feedback.get('username') else f"ID: {feedback['user_id']}"
    full_name = feedback.get('full_name', 'Не указано')

    # Используем Саратовское время
    saratov_time = DatabaseManager.format_saratov_time(feedback.get('created_at'))

    text = f"💬 <b>Отзыв #{feedback['id']}</b>\n\n"
    text += f"🪑 <b>Стол:</b> {table_number:02d}\n"
    text += f"👤 <b>Пользователь:</b> {user_info}\n"
    text += f"📛 <b>Имя:</b> {full_name}\n"
    text += f"📅 <b>Дата и время (Саратов):</b> {saratov_time}\n"
    text += f"📊 <b>Статус:</b> {status}\n\n"
    text += f"💭 <b>Сообщение:</b>\n{feedback['message']}"

    keyboard = []
    if feedback.get('status') == 'new':
        keyboard.append([InlineKeyboardButton(
            "✅ Пометить прочитанным",
            callback_data=f"feedback_markread_{feedback['id']}"
        )])

    keyboard.append([InlineKeyboardButton(
        "🗑 Удалить отзыв",
        callback_data=f"feedback_delete_{feedback['id']}"
    )])
    keyboard.append([InlineKeyboardButton("⬅️ Назад к списку", callback_data='view_feedback')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=reply_markup)


# --- КОМАНДЫ ДЛЯ АДМИНИСТРИРОВАНИЯ ---
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить администратора"""
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
        username = update.message.from_user.username or "Не указан"
        full_name = f"{update.message.from_user.first_name or ''} {update.message.from_user.last_name or ''}".strip()

        # Добавляем в базу
        success = DatabaseManager.add_admin(new_admin_id, username, full_name)

        if success:
            await update.message.reply_text(f"✅ Пользователь {new_admin_id} добавлен как администратор!")
        else:
            await update.message.reply_text("❌ Ошибка при добавлении администратора.")

    except ValueError:
        await update.message.reply_text("❌ Неверный формат user_id. user_id должен быть числом.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении админа: {e}")
        await update.message.reply_text("❌ Произошла ошибка при добавлении администратора.")


async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список администраторов"""
    user_id = update.message.from_user.id

    if not DatabaseManager.is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    admins = DatabaseManager.get_all_admins()

    if not admins:
        await update.message.reply_text("📋 Список администраторов пуст.")
        return

    admin_list = "📋 Список администраторов:\n\n"
    for admin in admins:
        admin_list += f"🆔 ID: {admin['user_id']}\n"
        admin_list += f"👤 Имя: {admin.get('full_name', 'Не указано')}\n"
        admin_list += f"📱 Username: @{admin.get('username', 'Не указан')}\n"
        admin_list += f"📅 Добавлен: {admin.get('created_at', 'Неизвестно')[:10]}\n"
        admin_list += "─" * 20 + "\n"

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

    # Обработка обновления листа
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

    # Обработка обратной связи
    if context.user_data.get('waiting_for_feedback'):
        table_number = context.user_data.get('selected_table', 'Не указан')
        username = update.message.from_user.username or ""
        full_name = f"{update.message.from_user.first_name or ''} {update.message.from_user.last_name or ''}".strip()

        success = DatabaseManager.add_feedback(user_id, username, full_name, text, table_number)

        # Очищаем данные пользователя
        if 'selected_table' in context.user_data:
            del context.user_data['selected_table']
        del context.user_data['waiting_for_feedback']

        if success:
            # Уведомляем администраторов о новом отзыве
            admins = DatabaseManager.get_all_admins()
            for admin in admins:
                try:
                    await context.bot.send_message(
                        chat_id=admin['user_id'],
                        text=f"🆕 Новый отзыв от @{username or 'без username'}\n🪑 Стол: {table_number:02d}\n\n{text[:500]}..."
                    )
                except Exception as e:
                    logger.error(f"Ошибка при уведомлении админа: {e}")

            await update.message.reply_text("✅ Спасибо за ваш отзыв! Мы его рассмотрим в ближайшее время.")
            await start(update, context)
        else:
            await update.message.reply_text("❌ Произошла ошибка при отправке отзыва. Попробуйте позже.")
        return


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
        application.add_handler(CallbackQueryHandler(button))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

        # Запуск бота
        logger.info("🤖 Бот запускается на Railway...")
        print("🚀 Restaurant Bot запущен на Railway!")
        print("📊 Мониторинг: https://railway.app")
        print("👑 Команды администратора:")
        print("   /add_admin <user_id> - Добавить администратора")
        print("   /list_admins - Показать список администраторов")
        print("   /remove_admin <user_id> - Удалить администратора")
        print("💬 Система обратной связи с выбором стола активирована")
        print("🪑 Доступны столы: 01-37 (красивая сетка 5x8)")
        print("⏰ Время отображается в Саратовском часовом поясе")
        print("🌶️ Красивое отображение остроты и аллергенов")
        print("⏱️ Время приготовления: 15 минут")
        print("🔙 Добавлены кнопки 'Назад' во всех меню")
        print("🍽️ Обновленное меню с салатами")

        application.run_polling()

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    main()