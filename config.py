import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла (для локальной разработки)
load_dotenv()

# Получаем переменные окружения (из Railway или из .env файла)
SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.environ.get("BOT_TOKEN") or os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID") or os.getenv("ADMIN_ID", 1466654401))

# Проверка обязательных переменных
missing_vars = []
if not SUPABASE_URL:
    missing_vars.append("SUPABASE_URL")
if not SUPABASE_KEY:
    missing_vars.append("SUPABASE_KEY")
if not BOT_TOKEN:
    missing_vars.append("BOT_TOKEN")

if missing_vars:
    error_msg = f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}"
    print(error_msg)
    print("💡 Для локальной разработки создайте файл .env с этими переменными")
    print("💡 На Railway добавьте их в настройках проекта")
    raise ValueError(error_msg)

# Инициализация Supabase
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase клиент успешно инициализирован")
    print(f"✅ Admin ID: {ADMIN_ID}")
    print("✅ Конфигурация загружена успешно")
except Exception as e:
    print(f"❌ Ошибка при инициализации Supabase: {e}")
    supabase = None