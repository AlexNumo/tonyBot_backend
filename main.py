import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

import config
import database
import handlers

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

async def handle_health(request):
    return web.Response(text="Bot is alive and polling!")

async def start_health_server():
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Веб-сервер перевірки працездатності запущено на порту {port}")

async def main():
    # Запуск веб-сервера перевірки працездатності для Render
    asyncio.create_task(start_health_server())

    # Ініціалізація клієнта бази даних Supabase
    logging.info("Клієнт Supabase успішно ініціалізований.")
    
    # Перевірка на шаблонний токен перед ініціалізацією бота
    if config.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logging.error("Критична помилка: Використовується шаблонний токен бота. Будь ласка, введіть дійсний токен у файлі .env")
        sys.exit(1)
        
    # Створення об'єкта бота з налаштуваннями за замовчуванням
    # Тут ми явно встановлюємо protect_content=True як глобальне налаштування для всіх відправлень
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            protect_content=True
        )
    )
    
    # Ініціалізація диспетчера
    dp = Dispatcher()
    
    # Підключення роутерів з обробниками
    dp.include_router(handlers.router)
    
    # Запуск отримання оновлень (polling)
    logging.info("Запуск бота...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот успішно зупинений користувачем.")
        sys.exit(0)
