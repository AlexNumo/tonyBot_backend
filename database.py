import asyncio
from supabase import create_client, Client
import config

# Ініціалізація клієнта Supabase
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

def _add_user_sync(user_id: int, username: str | None):
    """Синхронне додавання або оновлення користувача в Supabase."""
    data = {"user_id": user_id, "username": username}
    supabase.table("users").upsert(data).execute()

async def add_user(user_id: int, username: str | None):
    """Асинхронна обгортка для додавання користувача."""
    await asyncio.to_thread(_add_user_sync, user_id, username)


def _save_test_result_sync(user_id: int, score: int):
    """Синхронне збереження результатів тесту."""
    data = {"user_id": user_id, "score": score}
    supabase.table("test_results").insert(data).execute()

async def save_test_result(user_id: int, score: int):
    """Асинхронна обгортка для збереження результатів тесту."""
    await asyncio.to_thread(_save_test_result_sync, user_id, score)


def _save_lead_sync(user_id: int, package_name: str):
    """Синхронне збереження ліда (заявки на пакет участі)."""
    data = {"user_id": user_id, "package_name": package_name}
    supabase.table("leads").insert(data).execute()

async def save_lead(user_id: int, package_name: str):
    """Асинхронна обгортка для збереження ліда."""
    await asyncio.to_thread(_save_lead_sync, user_id, package_name)


def _get_packages_sync():
    """Синхронне отримання тарифів з таблиці packages."""
    response = supabase.table("packages").select("*").execute()
    # Сортуємо за ціною або залишаємо як є
    return response.data

async def get_packages():
    """Асинхронна обгортка для отримання тарифів."""
    return await asyncio.to_thread(_get_packages_sync)
