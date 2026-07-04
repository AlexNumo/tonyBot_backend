import os
from dotenv import load_dotenv

# Завантаження змінних оточення з файлу .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Валідація токена Telegram бота
if not BOT_TOKEN:
    raise ValueError("Помилка: BOT_TOKEN не знайдено у файлі .env або змінні оточення.")

if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
    print("Увага: Будь ласка, замініть 'YOUR_TELEGRAM_BOT_TOKEN' у файлі .env на ваш реальний токен від @BotFather.")

# Валідація налаштувань Supabase
if not SUPABASE_URL:
    raise ValueError("Помилка: SUPABASE_URL не знайдено у файлі .env.")

if not SUPABASE_KEY:
    raise ValueError("Помилка: SUPABASE_KEY не знайдено у файлі .env.")

# Додаткові налаштування для об'єднання ботів
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EXPRESS_API_URL = os.getenv("EXPRESS_API_URL", "http://localhost:3000")
LESSONS_FILE_PATH = os.getenv("LESSONS_FILE_PATH", "../tony_tg_bot-main/src/data/lessons.json")

if not GEMINI_API_KEY:
    print("Попередження: GEMINI_API_KEY не знайдено у файлі .env. ШІ-помічник працюватиме в режимі заглушки.")
