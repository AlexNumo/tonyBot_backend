from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os
import json
import re
import httpx
import config

import database

router = Router()

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
        "desc": "Побачити, що ти не в тупику, а на порозі нового етапу.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Робочий зошит"
    },
    2: {
        "title": "День 2. Що насправді забирає мою енергію.",
        "desc": "Знайти реальні джерела ресурсу в своєму дні, а не абстрактну втому.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Робочий зошит"
    },
    3: {
        "title": "День 3. Що я тримаю — і боюсь відпустити.",
        "desc": "Побачити ціну утримання старого і чесно назвати страх змін.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Робочий зошит"
    },
    4: {
        "title": "День 4. Зустріч із собою справжньою.",
        "desc": "Почути себе за межами ролей, очікувань і постійного 'треба'.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Робочий зошит"
    },
    5: {
        "title": "День 5. Точка відчаю.",
        "desc": "Новий урок! Як не загубити себе в лімінальному просторі «між» старим і новим.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Робочий зошит"
    },
    6: {
        "title": "День 6. Чому я не дозволяю собі більшого.",
        "desc": "Розпізнати внутрішню стелю, core beliefs (глибинні переконання) та установки, які обмежують наступний рівень.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Робочий зошит"
    },
    7: {
        "title": "День 7. Рішення вже є. Я просто боюсь його почути.",
        "desc": "Як розрізнити страх і справжнє «ні», увімкнути тілесний відгук і довіритись собі.\n\n🎬 Відео 15-20 хв\n🎧 Аудіо-практика\n📝 Робочий зошит"
    },
    8: {
        "title": "День 8. Інтеграція та фінал.",
        "desc": "Що змінюється, коли змінюєшся ти. Інтеграція всього тижня, захист від нейросаботажу та твій перший чесний крок.\n\n📊 : Аналіз та збірка\n✉️ : Практика «Лист собі»"
    }
}


def get_main_menu_keyboard():
    """Створення клавіатури головного меню."""
    builder = InlineKeyboardBuilder()
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
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"{config.EXPRESS_API_URL}/api/messages/save"
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


async def generate_gemini_response(user_prompt: str, username: str, api_key: str) -> str:
    """Генерує відповідь від імені Антоніни через Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
    
    system_instruction = (
        f"Ти — Антоніна, авторка та коуч психотерапевтичного практикуму з усвідомленості, медитації та емоційного балансу. \n"
        f"Твоє завдання — з теплотою, емпатією, любов'ю та професіоналізмом відповідати на повідомлення клієнтів. \n"
        f"Звертайся за нікнеймом ({username}) у дружній та довірливій формі. Давай короткі, надихаючі та змістовні відповіді виключно українською мовою. \n"
        f"Підтримуй користувача, якщо він переживає стрес, тривогу чи втому, ділися порадами з фокусування на диханні."
    )
    
    payload = {
        "contents": [{
            "parts": [{"text": user_prompt}]
        }],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                res_data = response.json()
                text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
            else:
                print(f"Gemini API status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Помилка виклику Gemini API: {e}")
        
    return "Дякую за повідомлення! Зберігайте спокій, дихайте глибоко. Я поруч. 🙏"


async def get_lessons():
    """Отримує матеріали занять через Express API, локальний файл або повертає дефолтні."""
    # 1. Спроба завантажити з Express API (підходить для продакшену на Render)
    if config.EXPRESS_API_URL:
        try:
            url = f"{config.EXPRESS_API_URL}/api/lessons"
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


# --- ОБРОБНИКИ КОМАНД ТА CALLBACK-ЗАПИТІВ ---

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обробник команди /start."""
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Синхронізація вхідного повідомлення
    await sync_message_to_express(user_id, "user", "/start")
    
    # Сповіщення адміна
    user_label = f"@{username}" if username else message.from_user.full_name
    await notify_admin_about_message(user_id, user_label, "/start", message.bot)
    
    # Збереження користувача в базі даних Supabase
    try:
        await database.add_user(user_id, username)
    except Exception as e:
        print(f"Помилка збереження користувача в БД: {e}")
        
    welcome_text = (
        f"Вітаю, {message.from_user.full_name}! ✨\n\n"
        "Рада бачити тебе тут. Я — провідник в онлайн-практикум **«Точка переходу»** Антоніни Пашко.\n\n"
        "Цей 7+1 денний практикум створений для жінок, у яких зовні все ніби добре, "
        "але всередині все частіше з'являється чесне відчуття: **так більше не хочу**.\n\n"
        "Обери цікавий розділ меню нижче, або почни з швидкого діагностичного тесту, "
        "щоб виявити, чи не блокує нейросаботаж твої справжні бажання."
    )
    
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(), protect_content=True)
    # Синхронізація відповіді
    await sync_message_to_express(user_id, "bot", welcome_text)


@router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """Повернення до головного меню."""
    await state.clear()
    user_id = callback.from_user.id
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
    else:
        lessons = await get_lessons()
        lesson = next((l for l in lessons if l.get("day") == day_num), None)
        if lesson:
            pdf_files = lesson.get("pdfFiles", [])
            pdf_str = "\n".join([f"• {f}" for f in pdf_files]) if pdf_files else "—"
            
            lesson_text = (
                f"🌸 *ПРАКТИКУМ «ТОЧКА ПЕРЕХОДУ» — ДЕНЬ {lesson.get('day')}* 🌸\n\n"
                f"✨ *Тема:* {lesson.get('title')}\n"
                f"📝 *Опис:* {lesson.get('description')}\n\n"
                f"🎥 *Відео-урок:* {lesson.get('videoDuration', '15-20 хв')}\n"
                f"🧘‍♀️ *Практика:* {lesson.get('practiceTitle', 'Аудіо-медитація')}\n\n"
                f"*Детальний зміст заняття:*\n{lesson.get('fullDescription', '')}\n\n"
                f"📂 *Завдання в робочому зошиті:*\n{pdf_str}"
            )
            await message.answer(lesson_text, parse_mode="Markdown")
            await sync_message_to_express(user_id, "bot", lesson_text)
        else:
            err_text = f"❌ Матеріали для дня {day_num} наразі недоступні."
            await message.answer(err_text)
            await sync_message_to_express(user_id, "bot", err_text)


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
        
    reply_text = f"✨ Дякую! Ваш номер телефону ({phone}) успішно перевірено та зареєстровано в базі.\n\nТепер ви повноправний учасник практикуму Антоніни! Напишіть будь-яке питання або очікуйте першого уроку."
    await message.answer(reply_text)
    await sync_message_to_express(user_id, "bot", reply_text)


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
        
    # Синхронізуємо вхідне повідомлення користувача
    await sync_message_to_express(user_id, "user", text)
    
    # Сповіщення адміна
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
        await message.answer(help_text, parse_mode="Markdown")
        await sync_message_to_express(user_id, "bot", help_text)
        return
        
    # Отримання відповіді від Gemini AI
    reply_text = "Дякую за повідомлення! Я обов'язково відповім вам найближчим часом. ✨"
    gemini_key = config.GEMINI_API_KEY
    if gemini_key:
        reply_text = await generate_gemini_response(text, username, gemini_key)
    else:
        # Спроба взяти дефолтну відповідь, якщо ключа немає
        reply_text = "Дякую за повідомлення! Я передам його Антоніні. 😊"
        
    await message.answer(reply_text)
    # Синхронізуємо відповідь бота
    await sync_message_to_express(user_id, "bot", reply_text)
