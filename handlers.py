from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

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

# Програма курсу по днях
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
        "desc": "Що змінюється, коли змінюєшся ти. Інтеграція всього тижня, захист від нейросаботажу та твій перший чесний крок.\n\n📊 Аналіз та збірка\n✉️ Практика «Лист собі»"
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


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обробник команди /start."""
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username
    
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


@router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """Повернення до головного меню."""
    await state.clear()
    welcome_text = (
        "Головне меню онлайн-практикуму **«Точка переходу»**.\n\n"
        "Обери розділ для ознайомлення з програмою, тестуванням чи тарифами."
    )
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "about_course")
async def process_about_course(callback: types.CallbackQuery):
    """Розділ 'Про практикум'."""
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


@router.callback_query(F.data == "about_author")
async def process_about_author(callback: types.CallbackQuery):
    """Розділ 'Про автора'."""
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


@router.callback_query(F.data == "contacts")
async def process_contacts(callback: types.CallbackQuery):
    """Розділ контакту."""
    text = (
        "❓ **Виникли запитання?**\n\n"
        "Якщо у вас залишилися питання щодо тарифів, програми чи процесу оплати, ви можете:\n\n"
        "📱 Написати Антоніні в Instagram: [Instagram @tonypashko](https://instagram.com/tonypashko)\n"
        "💬 Зв'язатися безпосередньо у Telegram: @tonypashko"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard(), parse_mode="Markdown", disable_web_page_preview=True)
    await callback.answer()


# --- РОЗДІЛ: ПРОГРАМА КУРСУ ---

@router.callback_query(F.data == "program_menu")
async def process_program_menu(callback: types.CallbackQuery):
    """Меню вибору дня програми."""
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


@router.callback_query(F.data.startswith("prog_day_"))
async def process_program_day(callback: types.CallbackQuery):
    """Деталі обраного дня."""
    day_num = int(callback.data.split("_")[-1])
    day_data = PROGRAM_DAYS[day_num]
    
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


# --- РОЗДІЛ: ДІАГНОСТИЧНИЙ ТЕСТ ---

@router.callback_query(F.data == "start_test")
async def process_start_test(callback: types.CallbackQuery, state: FSMContext):
    """Початок тесту на 7 ознак."""
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


@router.callback_query(TestStates.answering, F.data == "test_next")
async def show_question(callback: types.CallbackQuery, state: FSMContext):
    """Показ поточного питання."""
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
    else:
        # Безпековий перехід, якщо вийшли за межі
        await process_test_results(callback, state)
    await callback.answer()


@router.callback_query(TestStates.answering, F.data.startswith("ans_"))
async def process_answer(callback: types.CallbackQuery, state: FSMContext):
    """Обробка відповіді."""
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
    
    await callback.message.edit_text(result_title + result_desc, reply_markup=builder.as_markup())


# --- РОЗДІЛ: ТАРИФИ ТА ЗАПИС ---

@router.callback_query(F.data == "packages_menu")
async def process_packages_menu(callback: types.CallbackQuery):
    """Відображення тарифів (завантажуються динамічно з Supabase)."""
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
