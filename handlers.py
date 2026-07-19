from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import os
import asyncio
import json
import re
import httpx
import config

import database

router = Router()

# Словник для лімітування кількості щоденних запитів до ШІ (user_id -> (date, count))
user_ai_daily_tracker = {}

# Визначення станів для діагностичного тесту
class TestStates(StatesGroup):
    answering = State()

# Список запитань для тесту
TEST_QUESTIONS = [
    "Спокій з'являється тільки тоді, коли 'все встигла'?",
    "Відпочинок треба заслужити або пояснити собі, чому зараз можна?",
    "Автоматично береш на себе більше, ніж повинна?",
    "Легше дати, ніж попросити чи прийняти підтримку?",
    "Боляче, коли твої зусилля не помітили або не оцінили?",
    "Страшно розслабитись, ніби тоді все почне сипатися?",
    "Після досягнень швидко стає мало: треба більше, краще, ще один рівень?"
]

# Програма курсу по днях (для меню програми)
PROGRAM_DAYS = {
    1: {
        "title": "День 1. Я не втратила мотивацію. Я переросла.",
        "desc": "Побачити, що ти не в тупику, а на порозі нового етапу.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Текстова версія практики"
    },
    2: {
        "title": "День 2. Що насправді забирає мою енергію.",
        "desc": "Знайти реальні джерела ресурсу в своєму дні, а не абстрактну втому.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Текстова версія практики"
    },
    3: {
        "title": "День 3. Що я тримаю — і боюсь відпустити.",
        "desc": "Побачити ціну утримання старого і чесно назвати страх змін.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Текстова версія практики"
    },
    4: {
        "title": "День 4. Зустріч із собою справжньою.",
        "desc": "Почути себе за межами ролей, очікувань і постійного 'треба'.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Текстова версія практики"
    },
    5: {
        "title": "День 5. Точка відчаю.",
        "desc": "Новий урок! Як не загубити себе в лімінальному просторі «між» старим і новим.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Текстова версія практики"
    },
    6: {
        "title": "День 6. Чому я не дозволяю собі більшого.",
        "desc": "Розпізнати внутрішню стелю, core beliefs (глибинні переконання) та установки, які обмежують наступний рівень.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Текстова версія практики"
    },
    7: {
        "title": "День 7. Рішення вже є. Я просто боюсь його почути.",
        "desc": "Як розрізнити страх і справжнє «ні», увімкнути тілесний відгук і довіритись собі.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Текстова версія практики"
    },
    8: {
        "title": "День 8. Інтеграція та фінал.",
        "desc": "Що змінюється, коли змінюєшся ти. Інтеграція всього тижня, захист від нейросаботажу та твій перший чесний крок.\n\n📊 : Аналіз та збірка\n✉️ : Практика «Лист собі»"
    }
}


def get_main_menu_keyboard(is_paid: bool = False):
    """Створення клавіатури головного меню."""
    builder = InlineKeyboardBuilder()
    if is_paid:
        builder.button(text="📚 Мої зошити та бонуси", callback_data="my_workbooks")
    builder.button(text="ℹ️ Про практикум", callback_data="about_course")
    builder.button(text="📝 Пройти тест (7 ознак)", callback_data="start_test")
    builder.button(text="📅 Програма за днями", callback_data="program_menu")
    builder.button(text="👤 Про автора", callback_data="about_author")
    builder.button(text="💳 Тарифи та запис", callback_data="packages_menu")
    builder.button(text="❓ Задати питання", callback_data="contacts")
    builder.adjust(1)  # Всі кнопки в один стовпчик для зручності
    return builder.as_markup()


def get_back_to_menu_keyboard():
    """Клавіатура повернення на головну."""
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Головне меню", callback_data="main_menu")
    return builder.as_markup()


# --- СИНХРОНІЗАЦІЯ ІСТОРІЇ ПОВІДОМЛЕНЬ ТА ШІ-ФУНКЦІЇ ---

ADMIN_TELEGRAM_ID = 7780694746

async def sync_message_to_express(telegram_id: int, sender: str, text: str):
    """Надсилає повідомлення на Express сервер для збереження в історію та Supabase."""
    if not config.EXPRESS_API_URL:
        return
    try:
        # Очищаємо URL від зайвих символів '/' в кінці, щоб уникнути помилок 404
        express_url = config.EXPRESS_API_URL.rstrip('/')
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"{express_url}/api/messages/save"
            payload = {
                "telegramId": str(telegram_id),
                "sender": sender,
                "text": text
            }
            await client.post(url, json=payload)
    except Exception as e:
        print(f"Помилка синхронізації повідомлення для {telegram_id}: {e}")


async def notify_admin_about_message(user_id: int, username: str, text: str, bot):
    """Надсилає сповіщення адміністратору про нове повідомлення від користувача."""
    if user_id == ADMIN_TELEGRAM_ID:
        return
    admin_text = f"🔔 *Нове повідомлення від {username}* (ID: `{user_id}`):\n\n{text}"
    try:
        await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=admin_text, parse_mode="Markdown")
    except Exception as e:
        print(f"Помилка надсилання сповіщення адміну {ADMIN_TELEGRAM_ID}: {e}")


async def send_admin_bot_notification(text: str):
    """Надсилає сповіщення Антоніні та розробнику через спеціального адмін-бота."""
    if not config.ADMIN_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{config.ADMIN_BOT_TOKEN}/sendMessage"
    admin_ids = [7780694746, 216147493]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for admin_id in admin_ids:
            payload = {
                "chat_id": admin_id,
                "text": text,
                "parse_mode": "HTML"
            }
            try:
                await client.post(url, json=payload)
            except Exception as e:
                print(f"Помилка відправки через адмін-бота на {admin_id}: {e}")


async def generate_ai_response(user_prompt: str, username: str, history: list = None) -> str:
    """Генерує емпатичну відповідь від імені Антоніни через Groq або Gemini API."""
    gemini_key = config.GEMINI_API_KEY
    groq_key = config.GROQ_API_KEY
    
    system_instruction = (
        "Ти — Антоніна Пашко, практикуюча психологиня, коуч, енергопрактик та авторка 7+1 денного терапевтичного практикуму «Точка переходу».\n"
        "Твоє завдання — спілкуватися з учасницями практикуму з глибокою емпатією, любов'ю, підтримкою та професіоналізмом.\n"
        "Звертайся до користувачки за її ім'ям або нікнеймом ({username}) у дружній, довірливій формі. Відповідай виключно українською мовою.\n"
        "Будь гранично лаконічною: давай відповіді довжиною не більше 3-4 речень (максимум 70 слів).\n\n"
        "ПОВНА ІНФОРМАЦІЯ ПРО АВТОРКУ ТА ПРАКТИКУМ «ТОЧКА ПЕРЕХОДУ» (БАЗА ЗНАНЬ):\n\n"
        "1. ПРО АВТОРКУ (АНТОНІНА ПАШКО):\n"
        "- 17+ років практичного досвіду коучем, психологом та енергопрактиком.\n"
        "- 1350+ жінок, які пройшли трансформацію у її проєктах.\n"
        "- 70+ авторських проєктів для розвитку особистості.\n"
        "- Доктор філософії у сфері психології Кембриджської академії.\n"
        "- Гранд-доктор філософії в галузі інформаційних технологій (психологія).\n"
        "- Професорка психології та спікерка європейського рівня.\n"
        "- Працює з жінками, які стоять на межі змін — коли старе життя стало тісним, але немає ясності, як жити далі. Допомагає пройти внутрішні транзити без надриву та напруги.\n\n"
        "2. ПРО ПРАКТИКУМ ТА СУТЬ ТРАНСФОРМАЦІЇ:\n"
        "- Суть: Це не криза. Це точка переходу. Для жінок, у яких зовні все ніби добре, але всередині — «так більше не хочу».\n"
        "- Формат: 7+1 день, 15-30 хвилин на день, у власному темпі. Старт одразу після оплати, доступ залишається НАЗАВЖДИ.\n"
        "- Матеріали: 8 відео-уроків (15-20 хв), 8 аудіопрактик (медитації/тілесні практики на 10-15 хв), 2 варіанти Робочого зошита PDF з запитаннями для чесності з собою.\n"
        "- 5 Кроків Трансформації (від ілюзії до нової опори):\n"
        "  1) Ілюзія: Щось закінчилося -> Нова опора: Зі мною все гаразд — я на порозі масштабного нового.\n"
        "  2) Ілюзія: Звичний відпочинок не повертає сили -> Нова опора: Я чітко бачу, куди витікає енергія.\n"
        "  3) Ілюзія: Складно зрозуміти свої бажання -> Нова опора: Я знову чую свій внутрішній голос.\n"
        "  4) Ілюзія: Важливі рішення роками відкладаються -> Нова опора: Тотально довіряю собі та дію без сумнівів.\n"
        "  5) Ілюзія: Внутрішній крик «не хочу так жити» -> Нова опора: Я знаю свій наступний чесний автономний крок.\n\n"
        "3. ПРОГРАМА ПО ДНЯХ:\n"
        "- День 1: «Я не втратила мотивацію. Я переросла.» (Побачити, що ти не в тупику, а на порозі нового етапу).\n"
        "- День 2: «Що насправді забирає мою енергію.» (Знайти реальні джерела ресурсу в своєму дні).\n"
        "- День 3: «Що я тримаю — і боюсь відпустити.» (Побачити ціну утримання старого і назвати страх змін).\n"
        "- День 4: «Зустріч із собою справжньою.» (Почути себе за межами ролей, очікувань і постійного «треба»).\n"
        "- День 5: «Точка відчаю.» (Новий урок! Як не загубити себе в лімінальному просторі «між» старим і новим).\n"
        "- День 6: «Чому я не дозволяю собі більшого.» (Розпізнати внутрішню стелю, core beliefs та переконання).\n"
        "- День 7: «Рішення вже є. Я просто боюсь його почути.» (Тілесний відгук та довіра собі).\n"
        "- День 8: «Інтеграція та фінал.» (Захист від нейросаботажу, аналіз, практика «Лист собі»).\n\n"
        "4. ДІАГНОСТИКА (7 ОЗНАК прив'язаності цінності до корисності):\n"
        "1) Спокій з'являється тільки тоді, коли «все встигла».\n"
        "2) Відпочинок треба заслужити або пояснити собі, чому зараз можна.\n"
        "3) Автоматично береш на себе більше, ніж повинна.\n"
        "4) Легше дати, ніж просити чи прийняти підтримку.\n"
        "5) Боляче, коли твої зусилля не помітили або не оцінили.\n"
        "6) Страшно розслабитись, ніби тоді все почне сипатися.\n"
        "7) Після досягнень швидко стає мало: треба більше, краще, ще один рівень.\n\n"
        "5. ТАРИФИ ТА БОНУСИ:\n"
        "- 🟢 Самостійно (Базовий): 20€ (акція, замість 100€). 8 відео, 8 аудіо, робочий зошит, доступ назавжди, старт одразу + 3 бонуси.\n"
        "- 🔵 Зі спікером (Супровід): 125€ (замість 200€). Все з базового + Telegram-група з учасницями, голосові відповіді від Антоніни, 1 особиста Zoom-сесія з розбором запитів + 3 бонуси.\n"
        "- 🟣 Індивідуально (VIP Супровід): 400€ (замість 600€). Все з Супроводу + 4 особисті сесії в Zoom, особистий супровід у чаті 24/7, індивідуальна карта практик + 3 бонуси.\n"
        "- 🎁 Подарунки при оплаті: 1) Презентація «7 ознак, що заслуговуєш свою цінність», 2) Презентація «Сила без напруги», 3) Аудіопрактика-медитація «Повернення до себе».\n\n"
        "ПРАВИЛА ПОВЕДІНКИ:\n"
        "1. Підтримуй з любов'ю та розумінням. Якщо жінці важко — порадь повернути увагу в тіло та зробити повільний видих.\n"
        "2. Якщо запитують про матеріали уроків Днів 2-8, поясни, що вони відкриваються у процесі проходження або після оплати тарифу.\n"
        "3. Якщо користувачка просить покликати Антоніну чи зв'язати з нею особисто («хочу поговорити з Антоніною», «поклич Антоніну»), ввічливо дай відповідь і ОБОВ'ЯЗКОВО додай тег [CALL_HUMAN] на новому рядку для виклику автора."
    ).replace("{username}", username)

    # 1. Спроба використати Groq API (безкоштовно, без карти)
    if groq_key:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        
        # Будуємо масив повідомлень для контексту
        messages = [{"role": "system", "content": system_instruction}]
        if history:
            for msg in history:
                role = "user" if msg.get("sender") == "user" else "assistant"
                clean_text = msg.get("text", "").replace("[CALL_HUMAN]", "").strip()
                messages.append({"role": role, "content": clean_text})
        messages.append({"role": "user", "content": user_prompt})

        print(f"[Groq AI] Sending history context: {len(history)} messages. Current prompt: '{user_prompt}'")
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 250  # Обмеження вихідних токенів для економії ліміту
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    print(f"Groq API error {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Помилка запиту до Groq API: {e}")

    # 2. Спроба використати Gemini API (якщо налаштована)
    if gemini_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
        
        # Будуємо масив повідомлень для контексту Gemini
        contents = []
        if history:
            for msg in history:
                role = "user" if msg.get("sender") == "user" else "model"
                clean_text = msg.get("text", "").replace("[CALL_HUMAN]", "").strip()
                contents.append({"role": role, "parts": [{"text": clean_text}]})
        contents.append({"role": "user", "parts": [{"text": user_prompt}]})

        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_instruction}]}
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                else:
                    print(f"Gemini API status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Помилка виклику Gemini API: {e}")
        
    return "Дякую за повідомлення! Я обов'язково відповім вам особисто найближчим часом. Зберігайте спокій, зробіть глибокий вдих. Я поруч. 🙏 [CALL_HUMAN]"


async def get_lessons():
    """Отримує матеріали занять через Express API, локальний файл або повертає дефолтні."""
    # 1. Спроба завантажити з Express API (підходить для продакшену на Render)
    if config.EXPRESS_API_URL:
        try:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            url = f"{express_url}/api/lessons"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and isinstance(data.get("data"), list):
                        return data["data"]
        except Exception as e:
            print(f"Помилка отримання занять через Express API: {e}")

    # 2. Спроба завантажити з локального файлу (для локальної розробки)
    try:
        if os.path.exists(config.LESSONS_FILE_PATH):
            with open(config.LESSONS_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Помилка зчитування локального файлу занять: {e}")
        
    # Дефолтні заняття як резервна копія
    return [
        {
            "day": 1,
            "title": "Я не втратила мотивацію. Я переросла.",
            "description": "Побачити, що ти не в тупику, а на порозі нового етапу.",
            "videoDuration": "15-20 хв",
            "practiceTitle": "Практика: Я не втратила мотивацію. Я переросла.",
            "fullDescription": "Відео-урок розповість про першу ілюзію контролю — коли здається, що щось закінчилося, але ще незрозуміло що саме. Ми вибудовуємо нову опору: зі мною все гаразд, я просто на порозі масштабного нового етапу."
        },
        {
            "day": 2,
            "title": "Що насправді забирає мою енергію.",
            "description": "Знайти реальні джерела ресурсу в своєму дні, а не абстрактну втому.",
            "videoDuration": "15-20 хв",
            "practiceTitle": "Практика: Виявлення витоків енергії",
            "fullDescription": "Друга ілюзія контролю: звичний відпочинок більше не повертає сили. Нова опора: я чітко бачу, куди насправді витікає моя енергія і як прибрати фоновий шум."
        },
        {
            "day": 3,
            "title": "Що я тримаю — і боюсь відпустити.",
            "description": "Побачити ціну утримання старого і чесно назвати страх змін.",
            "videoDuration": "15-20 хв",
            "practiceTitle": "Практика: Ціна утримання старого",
            "fullDescription": "Коли стає занадто складно зрозуміти, чого хочеться насправді. Ми робимо крок у бік розкриття та чесного визнання страхів, які тримають нас на місці."
        },
        {
            "day": 4,
            "title": "Зустріч із собою справжньою.",
            "description": "Почути себе за межами ролей, очікувань і постійного «треба».",
            "videoDuration": "15-20 хв",
            "practiceTitle": "Практика: Хто я без моїх ролей",
            "fullDescription": "Зупинка і чесна розмова з собою. Вчимося чути власний внутрішній голос за межами чужого схвалення та соціальних ярликів."
        },
        {
            "day": 5,
            "title": "Точка відчаю.",
            "description": "Як не загубити себе в лімінальному просторі «між» старим і новим.",
            "videoDuration": "15-20 хв",
            "practiceTitle": "Практика: Лімінальний простір",
            "fullDescription": "Внутрішній крик: 'Я більше не хочу і не буду так жити'. Робота з точкою порожнечі, де старе вже пішло, а нове ще не з'явилося. Вчимося витримувати невизначеність."
        },
        {
            "day": 6,
            "title": "Чому я не дозволяю собі більшого.",
            "description": "Розпізнати внутрішню стелю, core beliefs та переконання, які обмежують наступний рівень.",
            "videoDuration": "15-20 хв",
            "practiceTitle": "Практика: Робота з обмежуючими переконаннями",
            "fullDescription": "Розкриття глибоких переконань про те, чому відпочинок треба заслуговувати, чому не можна просити про допомогу і чому небезпечно розслаблятися."
        },
        {
            "day": 7,
            "title": "Рішення вже є. Я просто боюсь його почути.",
            "description": "Як розрізнити страх і справжнє «ні», увімкнути тілесний відгук і довіритись собі.",
            "videoDuration": "15-20 хв",
            "practiceTitle": "Практика: Тілесний відгук",
            "fullDescription": "Повне з'єднання розуму і тіла. Коли важливі рішення роками відкладаються 'на потім', відповідь насправді вже всередині. Вчимося довіряти собі на 100%."
        },
        {
            "day": 8,
            "title": "Інтеграція та фінал.",
            "description": "Що змінюється, коли змінюєшся ти. Захист від нейросаботажу.",
            "videoDuration": "15-20 хв",
            "practiceTitle": "Практика «Лист собі»",
            "fullDescription": "Інтеграція всього тижня практикуму, захист від повернення до старих патернів і твій перший чесний, автономний крок у нове життя без надриву та напруги."
        }
    ]


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def find_day_files(day_num: int):
    """Шукає медіафайли для певного дня в папці Material."""
    day_folder = os.path.join(BASE_DIR, "Material", f"day {day_num}")
    if not os.path.exists(day_folder):
        return None
        
    try:
        files = os.listdir(day_folder)
    except Exception as e:
        print(f"Помилка сканування папки {day_folder}: {e}")
        return None
        
    photo_file = None
    video_file = None
    audio_file = None
    pdf_file = None
    
    for f in files:
        f_lower = f.lower()
        full_path = os.path.join(day_folder, f)
        if os.path.isdir(full_path):
            continue
            
        if f_lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
            photo_file = full_path
        elif f_lower.endswith((".mp4", ".mov", ".avi", ".mkv", ".3gp")):
            video_file = full_path
        elif f_lower.endswith((".mp3", ".m4a", ".wav", ".ogg")):
            audio_file = full_path
        elif f_lower.endswith(".pdf"):
            pdf_file = full_path
            
    return {
        "photo": photo_file,
        "video": video_file,
        "audio": audio_file,
        "document": pdf_file
    }


async def register_file_id_automatically(day_num: int, media_type: str, file_id: str, filename: str = None):
    """Автоматично реєструє file_id у файлі lessons.json через Express API."""
    try:
        lessons = await get_lessons()
        lesson = next((l for l in lessons if l.get("day") == day_num), None)
        if not lesson:
            return False
            
        if media_type == "photo":
            lesson["photoFileId"] = file_id
        elif media_type == "video":
            lesson["videoFileId"] = file_id
        elif media_type == "audio":
            lesson["audioFileId"] = file_id
        elif media_type == "document":
            lesson["pdfFileId"] = file_id
            if filename:
                lesson["pdfFiles"] = [filename]
            
        if config.EXPRESS_API_URL:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.put(f"{express_url}/api/lessons", json={"lessons": lessons})
                return res.status_code == 200
    except Exception as e:
        print(f"Помилка автореєстрації file_id: {e}")
    return False


# --- ОБРОБНИКИ КОМАНД ТА CALLBACK-ЗАПИТІВ ---

async def send_purchase_materials_to_user(bot, user_id: int):
    """Надсилає 2 варіанти робочого зошита та 3 бонуси оплаченому користувачу з інтервалом в 15 секунд."""
    congrats_text = (
        "<b>🎉 Вітаємо у практикумі «Точка переходу»!</b>\n\n"
        "Ваша оплата успішно отримана та доступ до програми активовано.\n\n"
        "Нижче ми надсилаємо вам обіцяні матеріали: <b>два варіанти Робочого зошита</b> практикуму "
        "(оберіть той, який вам зручніше заповнювати), а також <b>3 спеціальні бонуси</b>, "
        "які допоможуть вам підготуватися та пройти цей шлях максимально комфортно і глибоко. ✨\n\n"
        "<i>⏳ Для вашої зручності файли надходитимуть послідовно з інтервалом у 15 секунд.</i>"
    )
    try:
        await bot.send_message(chat_id=user_id, text=congrats_text, parse_mode="HTML")
        await sync_message_to_express(user_id, "bot", congrats_text)
    except Exception as e:
        print(f"Помилка надсилання вітання для {user_id}: {e}")
    
    await asyncio.sleep(3)

    async def send_single_file(file_path: str, media_type: str, caption: str):
        if not os.path.exists(file_path):
            print(f"Файл не знайдено: {file_path}")
            return
        input_file = FSInputFile(file_path)
        try:
            if media_type == "document":
                await bot.send_document(chat_id=user_id, document=input_file, caption=caption, protect_content=True)
            elif media_type == "audio":
                await bot.send_audio(chat_id=user_id, audio=input_file, caption=caption, protect_content=True)
        except Exception as ex:
            print(f"Помилка надсилання файлу {file_path}: {ex}")

    # 1. Зошит 1
    await send_single_file(
        "Material/Робочий_зошит_Точка_переходу.pdf",
        "document",
        "📚 Робочий зошит «Точка переходу» (Варіант 1)\n\nТвій особистий простір для роздумів, відкриттів та чесної розмови із собою."
    )
    await sync_message_to_express(user_id, "bot", "[Надіслано Робочий зошит PDF (Варіант 1)]")
    await asyncio.sleep(15)

    # 2. Зошит 2
    await send_single_file(
        "Material/Робочий_зошит_Точка_переходу_2.pdf",
        "document",
        "📚 Робочий зошит «Точка переходу» (Варіант 2)\n\nАльтернативний формат зошиту для зручного використання."
    )
    await sync_message_to_express(user_id, "bot", "[Надіслано Робочий зошит PDF (Варіант 2)]")
    await asyncio.sleep(15)

    # 3. Бонуси
    gifts = [
        ("Material/Gift/7_ОЗНАК_ЩО_ЗАСЛУГОВУЄШ_СВОЮ_ЦІННІСТЬ.pptx", "document", "🎁 Бонус 1: Презентація '7 ознак, що заслуговуєш свою цінність'"),
        ("Material/Gift/СИЛА без НАПРУГИ.pptx", "document", "🎁 Бонус 2: Презентація 'Сила без напруги'"),
        ("Material/Gift/ПРАКТИКА - Медитація подарунок.m4a", "audio", "🎁 Бонус 3: Аудіопрактика-медитація 'Повернення до себе'")
    ]

    for idx, (path_file, m_type, cap) in enumerate(gifts):
        await send_single_file(path_file, m_type, cap)
        await sync_message_to_express(user_id, "bot", f"[Надіслано бонус: {os.path.basename(path_file)}]")
        if idx < len(gifts) - 1:
            await asyncio.sleep(15)

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обробник команди /start."""
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Парсинг реферального UTM параметру або deep link параметру оплати (наприклад, /start pay_12345)
    utm_source = None
    utm_medium = None
    parts = message.text.split() if message.text else []
    if len(parts) > 1:
        start_param = parts[1].strip()
        if start_param.startswith("pay_"):
            order_ref = start_param.replace("pay_", "").strip()
            print(f"Deep link payment link detected for user {user_id}, order: {order_ref}")
            # Можна спробувати зв'язати замовлення за ref
        else:
            utm_source = start_param
            utm_medium = "telegram_bot"

    # Отримання посилання на аватарку
    avatar_url = None
    try:
        photos = await message.bot.get_user_profile_photos(user_id=user_id, limit=1)
        if photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id  # найбільша фотографія
            file = await message.bot.get_file(file_id)
            if file.file_path and config.BOT_TOKEN:
                avatar_url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file.file_path}"
    except Exception as e:
        print(f"Помилка отримання аватарки: {e}")

    # Синхронізація вхідного повідомлення
    await sync_message_to_express(user_id, "user", "/start")
    
    # Сповіщення адміна
    user_label = f"@{username}" if username else message.from_user.full_name
    await notify_admin_about_message(user_id, user_label, f"/start (utm: {utm_source})", message.bot)
    
    # Збереження користувача в базі даних із додатковими даними
    try:
        await database.add_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            avatar_url=avatar_url,
            utm_source=utm_source,
            utm_medium=utm_medium
        )
        # Логування дії користувача
        await database.log_user_action(
            user_id=user_id,
            action_type="command",
            target_element="/start",
            metadata={"utm_source": utm_source, "utm_medium": utm_medium}
        )
    except Exception as e:
        print(f"Помилка збереження користувача в БД: {e}")
        
    # Зчитуємо текст привітання з файлу або беремо стандартний
    welcome_text_path = os.path.join(BASE_DIR, "Material", "Вітальне повідомлення.txt")
    welcome_text = ""
    if os.path.exists(welcome_text_path):
        try:
            with open(welcome_text_path, "r", encoding="utf-8") as f:
                welcome_text = f.read()
        except Exception as e:
            print(f"Помилка зчитування файлу привітання: {e}")
            
    if not welcome_text:
        welcome_text = (
            f"Вітаю, {message.from_user.full_name}! ✨\n\n"
            "Рада бачити тебе тут. Я — провідник в онлайн-практикум **«Точка переходу»** Антоніни Пашко.\n\n"
            "Цей 7+1 денний практикум створений для жінок, у яких зовні все ніби добре, "
            "але всередині все частіше з'являється чесне відчуття: **так більше не хочу**.\n\n"
            "Обери цікавий розділ меню нижче, або почни з швидкого діагностичного тесту, "
            "об виявити, чи не блокує нейросаботаж твої справжні бажання."
        )

    # Перевіряємо наявність welcomePhotoFileId у першому уроці для надсилання вітального фото
    welcome_photo_id = None
    try:
        lessons = await get_lessons()
        if lessons and "welcomePhotoFileId" in lessons[0]:
            welcome_photo_id = lessons[0]["welcomePhotoFileId"]
    except Exception as e:
        print(f"Помилка отримання welcomePhotoFileId: {e}")
        
    # Якщо є зареєстроване фото — спочатку відправляємо його
    if welcome_photo_id:
        try:
            await message.answer_photo(photo=welcome_photo_id, protect_content=True)
            await sync_message_to_express(user_id, "bot", "[Надіслано вітальне фото]")
        except Exception as e:
            print(f"Помилка надсилання вітального фото: {e}")
            
    # Перевіряємо статус оплати користувача у Supabase / БД
    is_paid = False
    try:
        if database.supabase:
            res = await asyncio.to_thread(lambda: database.supabase.table("users").select("status").eq("user_id", user_id).maybe_single().execute())
            if res and res.data and res.data.get("status") in ["base", "support", "vip"]:
                is_paid = True
    except Exception as e:
        print(f"Помилка перевірки статусу для {user_id}: {e}")

    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(is_paid=is_paid), protect_content=True)
    await sync_message_to_express(user_id, "bot", welcome_text)

    # Якщо користувач зайшов за deep link оплати (pay_orderRef) щойно після покупки на сайті
    parts = message.text.split() if message.text else []
    if len(parts) > 1 and parts[1].strip().startswith("pay_"):
        await send_purchase_materials_to_user(message.bot, user_id)




@router.callback_query(F.data == "my_workbooks")
async def process_my_workbooks(callback: types.CallbackQuery):
    """Обробник кнопки 'Мої зошити та бонуси'."""
    user_id = callback.from_user.id
    await callback.answer("📂 Надсилаємо ваші зошити та бонуси...")
    await send_purchase_materials_to_user(callback.bot, user_id)

@router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """Повернення до головного меню."""
    await state.clear()
    user_id = callback.from_user.id
    await database.log_user_action(user_id, "click_button", "main_menu")
    await sync_message_to_express(user_id, "user", "[Клік: Головне меню]")
    
    welcome_text = (
        "Головне меню онлайн-практикуму **«Точка переходу»**.\n\n"
        "Обери розділ для ознайомлення з програмою, тестуванням чи тарифами."
    )
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())
    await callback.answer()
    await sync_message_to_express(user_id, "bot", welcome_text)


@router.callback_query(F.data == "about_course")
async def process_about_course(callback: types.CallbackQuery):
    """Розділ 'Про практикум'."""
    user_id = callback.from_user.id
    await database.log_user_action(user_id, "click_button", "about_course")
    await sync_message_to_express(user_id, "user", "[Клік: Про практикум]")
    
    text = (
        "🌟 **7+1 - денний онлайн-практикум «Точка переходу»**\n\n"
        "Це не криза. Це точка твого переходу до нового рівня життя.\n\n"
        "**Для кого цей практикум?**\n"
        "Для жінок, які зовні справляються та мають успіх, але всередині відчувають "
        "глибоку втому, потребу зупинитися і почати жити для себе, а не для відповідності чужим очікуванням.\n\n"
        "🔄 **Що зміниться (Трансформація):**\n"
        "1. *Ілюзія контролю:* Щось закінчилося, але ще незрозуміло що саме.\n"
        "   ➡️ **Нова опора:** Зі мною все гаразд — я на порозі масштабного нового.\n\n"
        "2. *Ілюзія контролю:* Звичний відпочинок більше не повертає сили.\n"
        "   ➡️ **Нова опора:** Я чітко бачу, куди насправді витікає моя енергія.\n\n"
        "3. *Ілюзія контролю:* Стало занадто складно зрозуміти, чого хочеться насправді.\n"
        "   ➡️ **Нова опора:** Я знову чую свій внутрішній голос та справжні бажання.\n\n"
        "⏱ **Формат:** 15-30 хвилин на день, проходження у власному темпі, доступ назавжди!"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Пройти тест (7 ознак)", callback_data="start_test")
    builder.button(text="📅 Програма", callback_data="program_menu")
    builder.button(text="↩️ Головне меню", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
    await sync_message_to_express(user_id, "bot", text)


@router.callback_query(F.data == "about_author")
async def process_about_author(callback: types.CallbackQuery):
    """Розділ 'Про автора'."""
    user_id = callback.from_user.id
    await database.log_user_action(user_id, "click_button", "about_author")
    await sync_message_to_express(user_id, "user", "[Клік: Про автора]")
    
    text = (
        "👤 **Антоніна Пашко — Авторка практикуму**\n\n"
        "Провідник у внутрішніх транзитах без надриву та напруги. Допомагає жінкам "
        "почути себе за межами ролей, очікувань та постійного 'треба'.\n\n"
        "🏆 **Регалії та цифри:**\n"
        "• **17+ років** практичного досвіду коучем, психологом та енергопрактиком.\n"
        "• **1350+ жінок**, які пройшли свій шлях трансформації та змін.\n"
        "• **70+ авторських проектів**, присвячених розвитку особистості.\n"
        "• Доктор філософії у сфері психології Кембриджської академії.\n"
        "• Гранд-доктор філософії в галузі інформаційних технологій (психологія).\n"
        "• Професорка психології та спікерка європейського рівня.\n\n"
        "💬 *«Мені важливо, щоб реальний внутрішній зсув ви відчули вже з першої практики.»*"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()
    await sync_message_to_express(user_id, "bot", text)


@router.callback_query(F.data == "contacts")
async def process_contacts(callback: types.CallbackQuery):
    """Розділ контакту."""
    user_id = callback.from_user.id
    await database.log_user_action(user_id, "click_button", "contacts")
    await sync_message_to_express(user_id, "user", "[Клік: Задати питання]")
    
    text = (
        "❓ **Виникли запитання?**\n\n"
        "Якщо у вас залишилися питання щодо тарифів, програми чи процесу оплати, ви можете:\n\n"
        "📱 Написати Антоніні в Instagram: [Instagram @tonypashko](https://instagram.com/tonypashko)\n"
        "💬 Зв'язатися безпосередньо у Telegram: @tonypashko"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard(), parse_mode="Markdown", disable_web_page_preview=True)
    await callback.answer()
    await sync_message_to_express(user_id, "bot", text)


# --- РОЗДІЛ: ПРОГРАМА КУРСУ ---

@router.callback_query(F.data == "program_menu")
async def process_program_menu(callback: types.CallbackQuery):
    """Меню вибору дня програми."""
    user_id = callback.from_user.id
    await database.log_user_action(user_id, "click_button", "program_menu")
    await sync_message_to_express(user_id, "user", "[Клік: Програма за днями]")
    
    text = (
        "📅 **Програма: 7+1 днів, які повертають контакт із собою**\n\n"
        "Кожен день містить відео, аудіо-практику та запитання в робочому зошиті. "
        "Обери день для детального ознайомлення:"
    )
    
    builder = InlineKeyboardBuilder()
    # Створюємо сітку кнопок для днів 1-8
    for day in range(1, 9):
        builder.button(text=f"День {day}", callback_data=f"prog_day_{day}")
    builder.button(text="↩️ Головне меню", callback_data="main_menu")
    builder.adjust(2, 2, 2, 2, 1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
    await sync_message_to_express(user_id, "bot", text)


@router.callback_query(F.data.startswith("prog_day_"))
async def process_program_day(callback: types.CallbackQuery):
    """Деталі обраного дня."""
    day_num = int(callback.data.split("_")[-1])
    day_data = PROGRAM_DAYS[day_num]
    user_id = callback.from_user.id
    
    await sync_message_to_express(user_id, "user", f"[Клік: Програма День {day_num}]")
    
    text = (
        f"📅 **{day_data['title']}**\n\n"
        f"🔍 **Практика:**\n{day_data['desc']}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ До програми", callback_data="program_menu")
    builder.button(text="💳 Тарифи та запис", callback_data="packages_menu")
    builder.button(text="↩️ Головне меню", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
    await sync_message_to_express(user_id, "bot", text)


# --- РОЗДІЛ: ДІАГНОСТИЧНИЙ ТЕСТ ---

@router.callback_query(F.data == "start_test")
async def process_start_test(callback: types.CallbackQuery, state: FSMContext):
    """Початок тесту на 7 ознак."""
    user_id = callback.from_user.id
    await sync_message_to_express(user_id, "user", "[Клік: Пройти тест]")
    
    await state.set_state(TestStates.answering)
    await state.update_data(current_question=0, score=0)
    
    intro_text = (
        "📝 **Діагностика: 7 ознак того, що твоя цінність прив'язана до справ**\n\n"
        "Спробуй відповісти максимально чесно перед собою. Кожна відповідь наблизить тебе до розуміння реального стану.\n\n"
        "Розпочинаємо?"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Почати тест", callback_data="test_next")
    builder.button(text="↩️ Скасувати", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(intro_text, reply_markup=builder.as_markup())
    await callback.answer()
    await sync_message_to_express(user_id, "bot", intro_text)


@router.callback_query(TestStates.answering, F.data == "test_next")
async def show_question(callback: types.CallbackQuery, state: FSMContext):
    """Показ поточного питання."""
    user_id = callback.from_user.id
    await sync_message_to_express(user_id, "user", "[Клік: Почати тест]")
    
    data = await state.get_data()
    q_index = data.get("current_question", 0)
    
    if q_index < len(TEST_QUESTIONS):
        q_text = f"❓ **Питання {q_index + 1} з {len(TEST_QUESTIONS)}**\n\n{TEST_QUESTIONS[q_index]}"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Так, це про мене", callback_data="ans_yes")
        builder.button(text="❌ Ні, це не про мене", callback_data="ans_no")
        builder.button(text="↩️ Перервати тест", callback_data="main_menu")
        builder.adjust(2, 1)
        
        await callback.message.edit_text(q_text, reply_markup=builder.as_markup())
        await sync_message_to_express(user_id, "bot", q_text)
    else:
        # Безпековий перехід, якщо вийшли за межі
        await process_test_results(callback, state)
    await callback.answer()


@router.callback_query(TestStates.answering, F.data.startswith("ans_"))
async def process_answer(callback: types.CallbackQuery, state: FSMContext):
    """Обробка відповіді."""
    user_id = callback.from_user.id
    ans_label = "Так, це про мене" if callback.data == "ans_yes" else "Ні, це не про мене"
    await sync_message_to_express(user_id, "user", f"[Клік: {ans_label}]")
    
    data = await state.get_data()
    q_index = data.get("current_question", 0)
    score = data.get("score", 0)
    
    # Збільшення балів, якщо обрано "Так"
    if callback.data == "ans_yes":
        score += 1
        
    q_index += 1
    await state.update_data(current_question=q_index, score=score)
    
    if q_index < len(TEST_QUESTIONS):
        # Наступне питання
        await show_question(callback, state)
    else:
        # Кінець тесту
        await process_test_results(callback, state)
    await callback.answer()


async def process_test_results(callback: types.CallbackQuery, state: FSMContext):
    """Розрахунок та збереження результатів тесту."""
    data = await state.get_data()
    score = data.get("score", 0)
    user_id = callback.from_user.id
    
    # Збереження в Supabase
    try:
        await database.save_test_result(user_id, score)
    except Exception as e:
        print(f"Помилка збереження результату тесту в Supabase: {e}")
        
    await state.clear()
    
    result_title = f"📊 **Твій результат: {score} з 7**\n\n"
    
    if score >= 3:
        result_desc = (
            "⚠️ **Це серйозний сигнал.**\n"
            "Твоя самооцінка та відчуття власної цінності все ще міцно прив'язані до корисності, "
            "результату, схвалення чи надмірних зусиль. Спокій приходить тільки тоді, коли все зроблено, "
            "а відпочинок відчувається як слабкість.\n\n"
            "**Важливо:** З тобою абсолютно все гаразд. Свого часу ці паттерни допомогли вижити. "
            "Але сьогодні вони забирають твою живість, енергію та обмежують розвиток.\n\n"
            "Практикум **«Точка переходу»** розроблений саме для того, щоб екологічно вийти з цього замкнутого кола."
        )
    else:
        result_desc = (
            "✅ **Гарний баланс.**\n"
            "Здається, ти маєш відносно здоровий контакт зі своїми потребами та не схильна "
            "повністю розчинятися у справах. Проте, якщо ти відчуваєш фонове бажання змін "
            "або шукаєш нові життєві орієнтири, практикум допоможе знайти необхідну ясність."
        )
        
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Подивитись програму", callback_data="program_menu")
    builder.button(text="💳 Пакети участі", callback_data="packages_menu")
    builder.button(text="↩️ Головне меню", callback_data="main_menu")
    builder.adjust(1)
    
    full_result_text = result_title + result_desc
    await callback.message.edit_text(full_result_text, reply_markup=builder.as_markup())
    await sync_message_to_express(user_id, "bot", full_result_text)


# --- РОЗДІЛ: ТАРИФИ ТА ЗАПИС ---

@router.callback_query(F.data == "packages_menu")
async def process_packages_menu(callback: types.CallbackQuery):
    """Відображення тарифів (завантажуються динамічно з Supabase)."""
    user_id = callback.from_user.id
    await sync_message_to_express(user_id, "user", "[Клік: Тарифи та запис]")
    
    try:
        packages = await database.get_packages()
    except Exception as e:
        print(f"Помилка завантаження тарифів з Supabase: {e}")
        packages = []
        
    # Якщо база порожня або сталася помилка, використовуємо резервні дані
    if not packages:
        text = (
            "💳 **Обери безпечний та комфортний формат участі:**\n\n"
            "🟢 **1. Самостійно (Базовий)**\n"
            "• Повне самостійне проходження у своєму темпі\n"
            "• 8 відео-уроків, 8 аудіопрактик, робочий зошит\n"
            "• Доступ назавжди + подарунки\n"
            "🔥 **Ціна: 20€** (замість ~~100€~~)\n\n"
            "🔵 **2. Зі спікером (Супровід)**\n"
            "• Все з базового пакета + живий контакт\n"
            "• Telegram-група з учасницями та голосові відповіді від Антоніни\n"
            "• **1 особиста сесія в Zoom** після проходження курсу\n"
            "🔥 **Ціна: 125€** (замість ~~200€~~) (Залишилося місць: 5)\n\n"
            "🟣 **3. VIP Супровід (Індивідуально)**\n"
            "• Все з пакета Супровід\n"
            "• **4 особисті сесії в Zoom** та особистий супровід 24/7\n"
            "🔥 **Ціна: 400€** (замість ~~600€~~) (Залишилося місць: 2)\n\n"
            "💡 *Старт одразу після оплати. Доступ залишається назавжди!*"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🟢 Базовий (20€)", callback_data="order_base")
        builder.button(text="🔵 Супровід (125€)", callback_data="order_support")
        builder.button(text="🟣 VIP (400€)", callback_data="order_vip")
        builder.button(text="↩️ Головне меню", callback_data="main_menu")
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
        await sync_message_to_express(user_id, "bot", text)
        return

    # Динамічне формування тексту тарифів
    text = "💳 **Обери безпечний та комфортний формат участі:**\n\n"
    builder = InlineKeyboardBuilder()
    
    emoji_map = {
        "base": "🟢",
        "support": "🔵",
        "vip": "🟣"
    }
    
    for pkg in packages:
        pkg_id = pkg.get("id")
        name = pkg.get("name")
        tag = pkg.get("tag", "")
        desc = pkg.get("desc_text", "")
        price = pkg.get("price")
        old_price = pkg.get("old_price")
        places = pkg.get("available_places")
        features = pkg.get("features", [])
        
        emoji = emoji_map.get(pkg_id, "🔸")
        
        features_list = ""
        if features:
            # handle both string split and array
            if isinstance(features, str):
                features_list = "\n".join([f"• {f.strip()}" for f in features.split(",")])
            elif isinstance(features, list):
                features_list = "\n".join([f"• {f}" for f in features])
            
        places_str = f" (Залишилося місць: **{places}**)" if places is not None else ""
        
        text += (
            f"{emoji} **{name} ({tag})**\n"
            f"{desc}\n"
            f"{features_list}\n"
            f"🔥 **Ціна: {price}** (замість ~~{old_price}~~){places_str}\n\n"
        )
        
        builder.button(text=f"{emoji} {name} ({price})", callback_data=f"order_{pkg_id}")
        
    text += "💡 *Старт одразу після оплати. Доступ залишається назавжди!*"
    
    builder.button(text="↩️ Головне меню", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()
    await sync_message_to_express(user_id, "bot", text)


@router.callback_query(F.data.startswith("order_"))
async def process_order(callback: types.CallbackQuery):
    """Обробка вибору пакету (збір ліда) та надання посилання на оплату."""
    package_map = {
        "base": "Базовий (Самостійно) - 20€",
        "support": "Супровід (Зі спікером) - 125€",
        "vip": "VIP (Індивідуально) - 400€"
    }
    
    payment_links = {
        "base": "https://secure.wayforpay.com/button/b2860b6ba58a1",
        "support": "https://secure.wayforpay.com/button/b2a8990c0471e",
        "vip": "https://secure.wayforpay.com/button/b23ef4af753b2"
    }
    
    pkg_key = callback.data.split("_")[-1]
    package_name = package_map.get(pkg_key, "Невідомий пакет")
    payment_url = payment_links.get(pkg_key)
    user_id = callback.from_user.id
    
    await sync_message_to_express(user_id, "user", f"[Клік: Замовити {package_name}]")
    
    # Збереження ліда в Supabase
    try:
        await database.save_lead(user_id, package_name)
    except Exception as e:
        print(f"Помилка збереження ліда в Supabase: {e}")
        
    success_text = (
        f"🎉 **Заявку на участь прийнято!**\n\n"
        f"Ви обрали пакет: **{package_name}**.\n\n"
        "Натисніть кнопку нижче, щоб перейти до безпечної оплати через платіжний сервіс **WayForPay**.\n\n"
        "Після здійснення оплати доступ до практикуму буде відкрито автоматично. "
        "Якщо у вас виникнуть питання, ви завжди можете зв'язатися з автором."
    )
    
    builder = InlineKeyboardBuilder()
    if payment_url:
        builder.button(text="💳 Оплатити через WayForPay", url=payment_url)
    builder.button(text="💬 Зв'язатися в Telegram", url="https://t.me/tonypashko")
    builder.button(text="↩️ Назад до тарифів", callback_data="packages_menu")
    builder.button(text="↩️ Головне меню", callback_data="main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(success_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()
    await sync_message_to_express(user_id, "bot", success_text)


# --- НОВІ ОБРОБНИКИ ДЛЯ ОБ'ЄДНАННЯ БОТІВ ---

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обробник команди /help."""
    user_id = message.from_user.id
    await sync_message_to_express(user_id, "user", "/help")
    
    # Сповіщення адміна
    user_label = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    await notify_admin_about_message(user_id, user_label, "/help", message.bot)
    
    help_text = (
        "🤖 *Помічник практикуму «Точка переходу»:*\n\n"
        "• /start — перезапустити бота та відкрити головне меню\n"
        "• /help — показати список команд\n"
        "• /day1 ... /day8 — отримати матеріали конкретного дня (доступно для оплачених тарифів)\n\n"
        "📩 Напишіть своє питання у цей чат, і Антоніна обов'язково відповість вам!"
    )
    await message.answer(help_text, parse_mode="Markdown")
    await sync_message_to_express(user_id, "bot", help_text)


@router.message(F.text.regexp(r"^/day(\d+)$"))
async def cmd_day(message: types.Message):
    """Обробник команд отримання уроків /day1 ... /day8."""
    match = re.match(r"^/day(\d+)$", message.text)
    if not match:
        return
    day_num = int(match.group(1))
    user_id = message.from_user.id
    
    await sync_message_to_express(user_id, "user", message.text)
    
    # Сповіщення адміна
    user_label = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    await notify_admin_about_message(user_id, user_label, message.text, message.bot)
    
    if day_num < 1 or day_num > 8:
        err_text = "❌ Невірний номер дня. Виберіть від /day1 до /day8."
        await message.answer(err_text)
        await sync_message_to_express(user_id, "bot", err_text)
        return
        
    # Перевірка статусу оплати користувача
    is_paid = False
    try:
        from database import supabase
        res = supabase.table("users").select("status").eq("user_id", user_id).maybe_single().execute()
        if res.data and res.data.get("status") != "free":
            is_paid = True
    except Exception as e:
        print(f"Помилка перевірки підписки користувача {user_id}: {e}")
        
    if not is_paid:
        block_text = f"🔒 *Матеріали [День {day_num}] заблоковано.*\n\nДля отримання доступу, будь ласка, придбайте один із пакетів участі в кабінеті нашого WebApp або зверніться безпосередньо до Антоніни Пашко."
        await message.answer(block_text, parse_mode="Markdown")
        await sync_message_to_express(user_id, "bot", block_text)
        await database.log_course_progress(user_id=user_id, day_num=day_num, delivery_type="command", status="failed", error_message="🔒 Неоплачений доступ (free)")
    else:
        lessons = await get_lessons()
        lesson = next((l for l in lessons if l.get("day") == day_num), None)
        
        # Перевірка наявності локальних файлів
        day_files = find_day_files(day_num)
        has_local_files = day_files and any(day_files.values())
        
        if not lesson and not has_local_files:
            err_text = f"❌ Матеріали для дня {day_num} наразі недоступні."
            await message.answer(err_text)
            await sync_message_to_express(user_id, "bot", err_text)
            return

        # 1. Надсилаємо вступне текстове повідомлення
        lesson_text = ""
        if lesson:
            pdf_files_list = lesson.get("pdfFiles", [])
            pdf_str = "\n".join([f"• {f}" for f in pdf_files_list]) if pdf_files_list else "—"
            lesson_text = (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌸 *ДЕНЬ {lesson.get('day')} • ПРАКТИКУМ «ТОЧКА ПЕРЕХОДУ»* 🌸\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✨ *Тема дня:*\n«{lesson.get('title')}»\n\n"
                f"📝 *Про що цей день:*\n{lesson.get('description')}\n\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"ℹ️ *МАТЕРІАЛИ ЗАНЯТТЯ:*\n"
                f"🎥 *Відео-урок:* {lesson.get('videoDuration', '15-20 хв')}\n"
                f"🧘‍♀️ *Практика:* {lesson.get('practiceTitle', 'Аудіо-медитація')}\n\n"
                f"📖 *Детальний зміст:*\n{lesson.get('fullDescription', '')}\n\n"
                f"📂 *Завдання в робочому зошиті:*\n{pdf_str}\n\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"🙏 Проходьте практику у зручному темпі!\n"
                f"Наступний урок буде надіслано автоматично."
            )
        else:
            lesson_text = f"🌸 *ДЕНЬ {day_num} • ПРАКТИКУМ «ТОЧКА ПЕРЕХОДУ»* 🌸\n\nЗавантаження матеріалів..."

        await message.answer(lesson_text, parse_mode="Markdown")
        await sync_message_to_express(user_id, "bot", lesson_text)
        
        # 2. Надсилаємо медіа-файли
        # Якщо в lessons.json збережені file_id — надсилаємо їх напряму (працює як в хмарі, так і локально)
        if lesson:
            # Спочатку Фото
            if lesson.get("photoFileId"):
                try:
                    await asyncio.sleep(15)
                    await message.answer_photo(photo=lesson.get("photoFileId"), caption="🖼 Зображення дня", protect_content=True)
                    await sync_message_to_express(user_id, "bot", "[Надіслано фото за file_id]")
                except Exception as e:
                    print(f"Помилка надсилання фото за file_id: {e}")
                    
            # Тепер Відео
            if lesson.get("videoFileId"):
                try:
                    await asyncio.sleep(15)
                    await message.answer_video(video=lesson.get("videoFileId"), caption="🎥 Відео-урок", protect_content=True)
                    await sync_message_to_express(user_id, "bot", "[Надіслано відео за file_id]")
                except Exception as e:
                    print(f"Помилка надсилання відео за file_id: {e}")
                    
            # Тепер Аудіо
            if lesson.get("audioFileId"):
                try:
                    await asyncio.sleep(15)
                    await message.answer_audio(audio=lesson.get("audioFileId"), caption="🧘‍♀️ Аудіо-практика", protect_content=True)
                    await sync_message_to_express(user_id, "bot", "[Надіслано аудіо за file_id]")
                except Exception as e:
                    print(f"Помилка надсилання адіо за file_id: {e}")
                    
            # Тепер Робочий зошит PDF
            if lesson.get("pdfFileId"):
                try:
                    await asyncio.sleep(15)
                    await message.answer_document(document=lesson.get("pdfFileId"), caption="📝 Текстова версія практики (якщо вам зручніше читати, ніж слухати)", protect_content=True)
                    await sync_message_to_express(user_id, "bot", "[Надіслано робочий зошит за file_id]")
                except Exception as e:
                    print(f"Помилка надсилання документа за file_id: {e}")

        # Якщо є локальні файли в папці, але для них ще немає file_id (перший запуск) —
        # завантажуємо їх з диска та автоматично зберігаємо їхні file_id на майбутнє
        if has_local_files:
            # Якщо фото є на диску, але немає в базі
            if day_files["photo"] and (not lesson or not lesson.get("photoFileId")):
                try:
                    loading_msg = await message.answer("🖼 Завантаження зображення...")
                    input_file = FSInputFile(day_files["photo"])
                    sent_msg = await message.answer_photo(photo=input_file, caption="🖼 Зображення дня", protect_content=True)
                    await loading_msg.delete()
                    await sync_message_to_express(user_id, "bot", f"[Завантажено локальне фото: {os.path.basename(day_files['photo'])}]")
                    await register_file_id_automatically(day_num, "photo", sent_msg.photo[-1].file_id)
                except Exception as e:
                    print(f"Помилка завантаження локального фото: {e}")

            # Якщо відео є на диску, але немає в базі
            if day_files["video"] and (not lesson or not lesson.get("videoFileId")):
                f_size = os.path.getsize(day_files["video"])
                if f_size < 50 * 1024 * 1024:
                    try:
                        loading_msg = await message.answer("🎥 Завантаження відео-уроку...")
                        input_file = FSInputFile(day_files["video"])
                        sent_msg = await message.answer_video(video=input_file, caption="🎥 Відео-урок", protect_content=True)
                        await loading_msg.delete()
                        await sync_message_to_express(user_id, "bot", f"[Завантажено локальне відео: {os.path.basename(day_files['video'])}]")
                        await register_file_id_automatically(day_num, "video", sent_msg.video.file_id)
                    except Exception as e:
                        print(f"Помилка завантаження локального відео: {e}")

            # Якщо аудіо є на диску, але немає в базі
            if day_files["audio"] and (not lesson or not lesson.get("audioFileId")):
                f_size = os.path.getsize(day_files["audio"])
                if f_size < 50 * 1024 * 1024:
                    try:
                        loading_msg = await message.answer("🧘‍♀️ Завантаження аудіо-практики...")
                        input_file = FSInputFile(day_files["audio"])
                        sent_msg = await message.answer_audio(audio=input_file, caption="🧘‍♀️ Аудіо-практика", protect_content=True)
                        await loading_msg.delete()
                        await sync_message_to_express(user_id, "bot", f"[Завантажено локальне аудіо: {os.path.basename(day_files['audio'])}]")
                        await register_file_id_automatically(day_num, "audio", sent_msg.audio.file_id)
                    except Exception as e:
                        print(f"Помилка завантаження локального аудіо: {e}")

            # Якщо документ є на диску, але немає в базі
            if day_files["document"] and (not lesson or not lesson.get("pdfFileId")):
                f_size = os.path.getsize(day_files["document"])
                if f_size < 50 * 1024 * 1024:
                    try:
                        loading_msg = await message.answer("📝 Завантаження текстової версії практики...")
                        input_file = FSInputFile(day_files["document"])
                        sent_msg = await message.answer_document(document=input_file, caption="📝 Текстова версія практики (якщо вам зручніше читати, ніж слухати)", protect_content=True)
                        await loading_msg.delete()
                        await sync_message_to_express(user_id, "bot", f"[Завантажено локальний документ: {os.path.basename(day_files['document'])}]")
                        await register_file_id_automatically(day_num, "document", sent_msg.document.file_id, os.path.basename(day_files["document"]))
                    except Exception as e:
                        print(f"Помилка завантаження локального документа: {e}")
        elif not lesson or not (lesson.get("photoFileId") or lesson.get("videoFileId") or lesson.get("audioFileId") or lesson.get("pdfFileId")):
            # Якщо локальних файлів немає і в базі немає зареєстрованих file_id
            info_msg = f"🌸 Матеріали для Дня {day_num} наразі готуються та будуть доступні найближчим часом."
            await message.answer(info_msg)
            await sync_message_to_express(user_id, "bot", info_msg)


        # Логування успішного прогресу проходження курсу
        await database.log_course_progress(user_id=user_id, day_num=day_num, delivery_type="command", status="delivered")


@router.message(F.contact)
async def process_contact(message: types.Message):
    """Обробник надісланого контакту (номера телефону)."""
    user_id = message.from_user.id
    phone = message.contact.phone_number
    if phone and not phone.startswith("+"):
        phone = "+" + phone
        
    await sync_message_to_express(user_id, "user", f"[Поділився контактом: {phone}]")
    
    # Сповіщення адміна
    user_label = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    await notify_admin_about_message(user_id, user_label, f"[Поділився контактом: {phone}]", message.bot)
    
    # Збереження телефону в базі
    try:
        await database.save_user_phone(user_id, phone)
    except Exception as e:
        print(f"Помилка збереження телефону для {user_id}: {e}")

    # Перевіряємо, чи є для цього телефону оплата на гостьовому записі
    paid_status = None
    try:
        paid_status = await database.check_and_link_guest_payment(user_id, phone)
    except Exception as e:
        print(f"Помилка зв'язування оплати гостя: {e}")

    if paid_status:
        # У користувача є гостьова оплата! Активуємо доступ та відправляємо матеріали
        package_names = {
            "base": "Базовий (Самостійно) - 20€",
            "support": "Супровід (Зі спікером) - 125€",
            "vip": "VIP (Індивідуально) - 400€"
        }
        package_name = package_names.get(paid_status, "Оплачений тариф")
        
        congrats_text = (
            f"🎉 **Вітаємо у практикумі «Точка переходу»!**\n\n"
            f"Ми знайшли вашу оплату на сайті за тарифом **{package_name}** та успішно активували доступ!\n\n"
            f"Нижче надсилаємо вам обіцяні матеріали: **два варіанти Робочого зошита** "
            f"(оберіть той, який вам зручніше заповнювати) та **3 спеціальні бонуси**, "
            f"які допоможуть вам пройти цей шлях максимально комфортно і глибоко. ✨"
        )
        await message.answer(congrats_text, parse_mode="Markdown")
        await sync_message_to_express(user_id, "bot", congrats_text)
        await asyncio.sleep(1)

        # Допоміжна функція для надсилання файлів
        async def send_file(file_path: str, media_type: str, caption: str):
            if not os.path.exists(file_path):
                print(f"Файл не знайдено: {file_path}")
                return
            input_file = FSInputFile(file_path)
            try:
                if media_type == "document":
                    await message.answer_document(document=input_file, caption=caption, protect_content=True)
                elif media_type == "audio":
                    await message.answer_audio(audio=input_file, caption=caption, protect_content=True)
            except Exception as ex:
                print(f"Помилка надсилання файлу {file_path}: {ex}")

        # Надсилаємо Робочий зошит 1
        print(f"Sending workbook 1 to {user_id}...")
        await send_file(
            "Material/Робочий_зошит_Точка_переходу.pdf", 
            "document", 
            "📚 Робочий зошит «Точка переходу» (Варіант 1)\n\nТвій особистий простір для роздумів, відкриттів та чесної розмови із собою."
        )
        await sync_message_to_express(user_id, "bot", "[Надіслано Робочий зошит PDF (Варіант 1)]")
        await asyncio.sleep(1.5)

        # Надсилаємо Робочий зошит 2
        print(f"Sending workbook 2 to {user_id}...")
        await send_file(
            "Material/Робочий_зошит_Точка_переходу_2.pdf", 
            "document", 
            "📚 Робочий зошит «Точка переходу» (Варіант 2)\n\nАльтернативний формат зошиту для зручного використання."
        )
        await sync_message_to_express(user_id, "bot", "[Надіслано Робочий зошит PDF (Варіант 2)]")
        await asyncio.sleep(2)

        # Надсилаємо бонуси
        gifts = [
            ("Material/Gift/7_ОЗНАК_ЩО_ЗАСЛУГОВУЄШ_СВОЮ_ЦІННІСТЬ.pptx", "document", "🎁 Бонус 1: Презентація '7 ознак, що заслуговуєш свою цінність'"),
            ("Material/Gift/СИЛА без НАПРУГИ.pptx", "document", "🎁 Бонус 2: Презентація 'Сила без напруги'"),
            ("Material/Gift/ПРАКТИКА - Медитація подарунок.m4a", "audio", "🎁 Бонус 3: Аудіопрактика-медитація 'Повернення до себе'")
        ]

        for path_file, m_type, cap in gifts:
            print(f"Sending gift {path_file} to {user_id}...")
            await send_file(path_file, m_type, cap)
            await sync_message_to_express(user_id, "bot", f"[Надіслано бонус: {os.path.basename(path_file)}]")
            await asyncio.sleep(2)

        # Сповіщення адміна
        await send_admin_bot_notification(
            f"⚡ <b>Користувач зв'язав свій Telegram-профіль з оплатою на сайті!</b>\n\n"
            f"👤 <b>Користувач:</b> {user_label} (ID: {user_id})\n"
            f"📞 <b>Телефон:</b> <code>{phone}</code>\n"
            f"★ <b>Отриманий статус:</b> <code>{paid_status}</code>\n"
            f"★ Гостьовий запис успішно видалено."
        )
    else:
        # Звичайний користувач без попередньої оплати
        reply_text = f"✨ Дякую! Ваш номер телефону ({phone}) успішно перевірено та зареєстровано в базі.\n\nТепер ви повноправний учасник практикуму Антоніни! Напишіть будь-яке питання або очікуйте першого уроку."
        await message.answer(reply_text)
        await sync_message_to_express(user_id, "bot", reply_text)


@router.message(F.chat.id == ADMIN_TELEGRAM_ID, F.caption.startswith("#upload"))
async def handle_admin_media_upload(message: types.Message):
    """
    Обробник автоматичного завантаження медіафайлів від адміна.
    Формат підпису: #upload [day_X] [type] або #upload [welcome] [photo]
    де type може бути: photo, video, audio, document
    """
    caption = message.caption
    
    # Парсимо день та тип
    match = re.search(r"#upload\s+\[(day_\d+|welcome)\]\s+\[(\w+)\]", caption)
    if not match:
        await message.answer("❌ Некоректний формат підпису. Має бути: `#upload [day_X] [type]` або `#upload [welcome] [photo]`")
        return
        
    day_key = match.group(1)
    media_type = match.group(2).lower()
    
    file_id = None
    if media_type == "photo" and message.photo:
        file_id = message.photo[-1].file_id
    elif media_type == "video" and message.video:
        file_id = message.video.file_id
    elif media_type == "audio" and message.audio:
        file_id = message.audio.file_id
    elif media_type == "document" and message.document:
        file_id = message.document.file_id
    else:
        await message.answer(f"❌ Медіафайл не відповідає вказаному типу [{media_type}]")
        return
        
    # Оновлюємо lessons.json через Express API
    try:
        lessons = await get_lessons()
        if not lessons:
            await message.answer("❌ Список занять порожній.")
            return
            
        if day_key == "welcome":
            # Зберігаємо welcomePhotoFileId у першому уроці (як глобальний параметр)
            for lesson in lessons:
                lesson["welcomePhotoFileId"] = file_id
        else:
            day_num = int(day_key.replace("day_", ""))
            lesson = next((l for l in lessons if l.get("day") == day_num), None)
            if not lesson:
                await message.answer(f"❌ День {day_num} не знайдено в списку занять.")
                return
                
            if media_type == "photo":
                lesson["photoFileId"] = file_id
            elif media_type == "video":
                lesson["videoFileId"] = file_id
            elif media_type == "audio":
                lesson["audioFileId"] = file_id
            elif media_type == "document":
                lesson["pdfFileId"] = file_id
                if message.document and message.document.file_name:
                    lesson["pdfFiles"] = [message.document.file_name]
                
        # Відправляємо оновлений масив назад на Express
        if config.EXPRESS_API_URL:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.put(f"{express_url}/api/lessons", json={"lessons": lessons})
                if res.status_code == 200:
                    await message.answer(f"✅ Успішно зареєстровано {media_type} для {day_key}!")
                else:
                    await message.answer(f"❌ Помилка збереження на Express: {res.text}")
        else:
            await message.answer("❌ EXPRESS_API_URL не налаштовано, не вдалося зберегти зміни.")
    except Exception as e:
        await message.answer(f"❌ Виникла помилка при реєстрації файлу: {e}")


@router.message(F.text)
async def process_general_text(message: types.Message, state: FSMContext):
    """Обробник звичайних текстових повідомлень (ШІ-асистент Gemini)."""
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else f"@user_{user_id}"
    text = message.text
    
    # Ігноруємо команди, оскільки вони мають власні обробники
    if text.startswith("/"):
        return
        
    # Перевіряємо чи триває активний стан (тестування тощо)
    current_state = await state.get_state()
    if current_state is not None:
        return
        
    # Сповіщення адміна (просте сповіщення про факт повідомлення)
    user_label = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    await notify_admin_about_message(user_id, user_label, text, message.bot)
    
    # Ручна обробка текстового запиту про допомогу
    if text.lower() in ["help", "допомога"]:
        help_text = (
            "🤖 *Помічник практикуму «Точка переходу»:*\n\n"
            "• /start — перезапустити бота та відкрити головне меню\n"
            "• /help — показати список команд\n"
            "• /day1 ... /day8 — отримати матеріали конкретного дня (доступно для оплачених тарифів)\n\n"
            "📩 Напишіть своє питання у цей чат, і Антоніна обов'язково відповість вам!"
        )
        await sync_message_to_express(user_id, "user", text)
        await message.answer(help_text, parse_mode="Markdown")
        await sync_message_to_express(user_id, "bot", help_text)
        return
        
    # Лімітування кількості запитів до ШІ на добу (максимум 15 повідомлень)
    from datetime import date
    today = date.today()
    user_tracker = user_ai_daily_tracker.get(user_id)
    
    user_link = f"https://t.me/{message.from_user.username}" if message.from_user.username else f"tg://user?id={user_id}"
    user_name_display = message.from_user.full_name

    if user_tracker and user_tracker[0] == today:
        current_count = user_tracker[1]
        if current_count >= 15:
            limit_msg = (
                "⚠️ *Ви перевищили ліміт щоденних звернень до ШІ-асистента (макс. 15 повідомлень на добу).*\n\n"
                "Ваш запит перенаправлено Антоніні особисто. Вона відповість вам найближчим часом! 🙏"
            )
            await sync_message_to_express(user_id, "user", text)
            await message.answer(limit_msg, parse_mode="Markdown")
            await sync_message_to_express(user_id, "bot", limit_msg)
            # Форсуємо виклик адміністратора для відповіді через спеціального адмін-бота
            try:
                admin_warning = (
                    f"🚨 <b>Користувач перевищив ліміт ШІ і очікує відповіді!</b>\n\n"
                    f"👤 <b>Ім'я:</b> {user_name_display}\n"
                    f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
                    f"💬 <b>Нікнейм:</b> @{message.from_user.username if message.from_user.username else 'відсутній'}\n\n"
                    f"<b>Запит:</b> <i>\"{text}\"</i>\n\n"
                    f"👉 <a href=\"{user_link}\"><b>ВІДКРИТИ ДІАЛОГ З КОРИСТУВАЧЕМ</b></a>"
                )
                await send_admin_bot_notification(admin_warning)
            except Exception:
                pass
            return
        else:
            user_ai_daily_tracker[user_id] = (today, current_count + 1)
    else:
        user_ai_daily_tracker[user_id] = (today, 1)

    # 1. Спочатку отримуємо попередній діалог користувача з бази даних (ще без поточного повідомлення!)
    history = []
    try:
        history = await database.get_user_messages(user_id, limit=6)
    except Exception as e:
        print(f"Помилка отримання історії для ШІ: {e}")

    # 2. Тепер синхронізуємо вхідне повідомлення користувача в базу (після отримання історії)
    await sync_message_to_express(user_id, "user", text)

    # Отримання відповіді від ШІ (Groq Llama-3 або Gemini) з урахуванням історії
    reply_text = "Дякую за повідомлення! Я обов'язково відповім вам найближчим часом. ✨"
    if config.GROQ_API_KEY or config.GEMINI_API_KEY:
        reply_text = await generate_ai_response(text, username, history)
    else:
        # Спроба взяти дефолтну відповідь, якщо ключа немає
        reply_text = "Дякую за повідомлення! Я передам його Антоніні. 😊 [CALL_HUMAN]"
        
    # Регулярні вирази для форсування виклику людини (fail-safe)
    escalation_keywords = [
        "поклич", "покличте", "зв'язатися", "зв'язок", "адмін", "адміністратор", 
        "не проходить оплата", "помилка оплати", "оплата не", "не працює оплата",
        "wayforpay", "проблема з оплатою", "передай антоніні", "хочу поговорити з", "покличте автора", "покличте антоніну", "поклич антоніну"
    ]
    force_human = any(kw in text.lower() for kw in escalation_keywords)

    need_human = False
    if "[CALL_HUMAN]" in reply_text or force_human:
        need_human = True
        reply_text = reply_text.replace("[CALL_HUMAN]", "").strip()
        # Додаємо екологічну ремарку користувачу, якщо її ще немає в тексті відповіді
        if "покликала Антоніну" not in reply_text:
            reply_text += "\n\n*(я вже покликала Антоніну, вона відповість особисто найближчим часом)*"
        
    await message.answer(reply_text)
    # Синхронізуємо відповідь бота
    await sync_message_to_express(user_id, "bot", reply_text)

    if need_human:
        try:
            admin_warning = (
                f"🚨 <b>Користувач потребує особистої відповіді!</b>\n\n"
                f"👤 <b>Ім'я:</b> {user_name_display}\n"
                f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
                f"💬 <b>Нікнейм:</b> @{message.from_user.username if message.from_user.username else 'відсутній'}\n\n"
                f"<b>Запит:</b> <i>\"{text}\"</i>\n\n"
                f"👉 <a href=\"{user_link}\"><b>ВІДКРИТИ ДІАЛОГ З КОРИСТУВАЧЕМ</b></a>"
            )
            await send_admin_bot_notification(admin_warning)
        except Exception as e:
            print(f"Помилка надсилання сповіщення адміну: {e}")
