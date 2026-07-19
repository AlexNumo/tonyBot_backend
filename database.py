import asyncio
import httpx
from supabase import create_client, Client
import config

# Ініціалізація клієнта Supabase (якщо налаштований)
supabase: Client = None
try:
    if config.SUPABASE_URL and config.SUPABASE_KEY:
        supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
except Exception as e:
    print(f"Supabase client initialization skipped: {e}")

async def add_user(
    user_id: int, 
    username: str | None, 
    first_name: str | None = None, 
    last_name: str | None = None, 
    avatar_url: str | None = None, 
    utm_source: str | None = None, 
    utm_medium: str | None = None, 
    is_blocked: bool | None = None
):
    """Додає або оновлює користувача через Express API або Supabase."""
    if config.EXPRESS_API_URL:
        try:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            payload = {
                "telegramId": str(user_id),
                "username": username or f"user_{user_id}"
            }
            if first_name is not None: payload["firstName"] = first_name
            if last_name is not None: payload["lastName"] = last_name
            if avatar_url is not None: payload["avatarUrl"] = avatar_url
            if utm_source is not None: payload["utmSource"] = utm_source
            if utm_medium is not None: payload["utmMedium"] = utm_medium
            if is_blocked is not None: payload["isBlocked"] = is_blocked

            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{express_url}/api/users",
                    json=payload
                )
                if res.status_code == 200:
                    return
        except Exception as e:
            print(f"Помилка запису користувача через Express API: {e}")

    if supabase:
        try:
            existing_res = await asyncio.to_thread(lambda: supabase.table("users").select("status, phone").eq("user_id", user_id).maybe_single().execute())
            data = {"user_id": user_id, "username": username or f"user_{user_id}"}
            
            if existing_res and existing_res.data:
                if existing_res.data.get("status"):
                    data["status"] = existing_res.data.get("status")
                if existing_res.data.get("phone"):
                    data["phone"] = existing_res.data.get("phone")
            else:
                data["status"] = "free"

            if first_name is not None: data["first_name"] = first_name
            if last_name is not None: data["last_name"] = last_name
            if avatar_url is not None: data["avatar_url"] = avatar_url
            if utm_source is not None: data["utm_source"] = utm_source
            if utm_medium is not None: data["utm_medium"] = utm_medium
            if is_blocked is not None: data["is_blocked"] = is_blocked
            await asyncio.to_thread(lambda: supabase.table("users").upsert(data).execute())
        except Exception as e:
            print(f"Помилка запису користувача через Supabase: {e}")


async def save_test_result(user_id: int, score: int):
    """Зберігає результати тесту через Express API або Supabase."""
    if config.EXPRESS_API_URL:
        try:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{express_url}/api/test-results",
                    json={
                        "telegramId": str(user_id),
                        "score": score
                    }
                )
                if res.status_code == 200:
                    return
        except Exception as e:
            print(f"Помилка запису результату тесту через Express API: {e}")

    if supabase:
        try:
            data = {"user_id": user_id, "score": score}
            await asyncio.to_thread(lambda: supabase.table("test_results").insert(data).execute())
        except Exception as e:
            print(f"Помилка запису результату тесту через Supabase: {e}")


async def save_lead(user_id: int, package_name: str):
    """Зберігає ліда через Express API або Supabase."""
    if config.EXPRESS_API_URL:
        try:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{express_url}/api/leads",
                    json={
                        "telegramId": str(user_id),
                        "packageName": package_name
                    }
                )
                if res.status_code == 200:
                    return
        except Exception as e:
            print(f"Помилка запису ліда через Express API: {e}")

    if supabase:
        try:
            data = {"user_id": user_id, "package_name": package_name}
            await asyncio.to_thread(lambda: supabase.table("leads").insert(data).execute())
        except Exception as e:
            print(f"Помилка запису ліда через Supabase: {e}")


async def get_packages():
    """Отримує тарифи з Express API або Supabase."""
    if config.EXPRESS_API_URL:
        try:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{express_url}/api/packages")
                if res.status_code == 200:
                    data = res.json()
                    if data.get("success") and isinstance(data.get("data"), list):
                        return data["data"]
        except Exception as e:
            print(f"Помилка отримання тарифів через Express API: {e}")

    if supabase:
        try:
            response = await asyncio.to_thread(lambda: supabase.table("packages").select("*").execute())
            return response.data
        except Exception as e:
            print(f"Помилка отримання тарифів через Supabase: {e}")
            
    # Дефолтні тарифи, якщо нічого не доступно
    return [
        {"id": "base", "name": "Базовий", "price": "1900 грн", "description": "Доступ до занять без супроводу"},
        {"id": "support", "name": "Супровід", "price": "4900 грн", "description": "Доступ до занять та зворотній зв'язок"},
        {"id": "vip", "name": "VIP", "price": "12000 грн", "description": "Особиста робота з автором"}
    ]


async def save_user_phone(user_id: int, phone: str):
    """Оновлює телефон користувача через Express API або Supabase."""
    if config.EXPRESS_API_URL:
        try:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{express_url}/api/users",
                    json={
                        "telegramId": str(user_id),
                        "phone": phone
                    }
                )
                if res.status_code == 200:
                    return
        except Exception as e:
            print(f"Помилка запису телефону користувача через Express API: {e}")

    if supabase:
        try:
            await asyncio.to_thread(lambda: supabase.table("users").update({"phone": phone}).eq("user_id", user_id).execute())
        except Exception as e:
            print(f"Помилка запису телефону користувача через Supabase: {e}")


async def log_user_action(user_id: int, action_type: str, target_element: str | None = None, metadata: dict | None = None):
    """Логує дії та кліки користувача."""
    if config.EXPRESS_API_URL:
        try:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{express_url}/api/logs/action",
                    json={
                        "telegramId": str(user_id),
                        "actionType": action_type,
                        "targetElement": target_element or "",
                        "metadata": metadata or {}
                    }
                )
        except Exception as e:
            print(f"Помилка логування дії користувача через Express API: {e}")

    if supabase:
        try:
            data = {
                "user_id": user_id,
                "action_type": action_type,
                "target_element": target_element or "",
                "metadata": metadata or {}
            }
            await asyncio.to_thread(lambda: supabase.table("user_actions").insert(data).execute())
        except Exception as e:
            print(f"Помилка логування дії користувача через Supabase: {e}")


async def log_course_progress(user_id: int, day_num: int, delivery_type: str = "auto", status: str = "delivered", error_message: str | None = None):
    """Логує етапи проходження курсу."""
    if config.EXPRESS_API_URL:
        try:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{express_url}/api/logs/progress",
                    json={
                        "telegramId": str(user_id),
                        "dayNum": day_num,
                        "deliveryType": delivery_type,
                        "status": status,
                        "errorMessage": error_message
                    }
                )
        except Exception as e:
            print(f"Помилка логування прогресу курсу через Express API: {e}")

    if supabase:
        try:
            data = {
                "user_id": user_id,
                "day_num": day_num,
                "delivery_type": delivery_type,
                "status": status,
                "error_message": error_message
            }
            await asyncio.to_thread(lambda: supabase.table("course_progress_logs").insert(data).execute())
        except Exception as e:
            print(f"Помилка логування прогресу курсу через Supabase: {e}")


async def get_user_messages(user_id: int, limit: int = 10) -> list:
    """Отримує останні повідомлення користувача для контексту ШІ."""
    if config.EXPRESS_API_URL:
        try:
            express_url = config.EXPRESS_API_URL.rstrip('/')
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{express_url}/api/messages/{user_id}")
                if res.status_code == 200:
                    data = res.json()
                    if data.get("success") and isinstance(data.get("data"), list):
                        # Повертаємо останні N повідомлень
                        return data["data"][-limit:]
        except Exception as e:
            print(f"Помилка отримання повідомлень з Express API: {e}")

    if supabase:
        try:
            # Отримуємо повідомлення безпосередньо з Supabase
            response = await asyncio.to_thread(
                lambda: supabase.table("messages")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            if response.data:
                # Повертаємо у хронологічному порядку (від старіших до новіших)
                mapped = []
                for m in reversed(response.data):
                    mapped.append({
                        "sender": "user" if m["direction"] == "user" else "bot",
                        "text": m["text"]
                    })
                return mapped
        except Exception as e:
            print(f"Помилка отримання повідомлень з Supabase: {e}")

    return []


async def check_and_link_guest_payment(user_id: int, phone: str) -> str | None:
    """
    Перевіряє, чи є гостьовий запис оплати для цього телефону.
    Якщо є, переносить статус на real user_id, оновлює ліди,
    видаляє гостьовий запис і повертає статус тарифу.
    """
    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) < 9:
        return None
        
    guest_id = int(clean_phone[-10:])
    
    if supabase:
        try:
            # Шукаємо гостьовий запис
            res = await asyncio.to_thread(
                lambda: supabase.table("users").select("*").eq("user_id", guest_id).maybe_single().execute()
            )
            if res.data and res.data.get("status") != "free":
                status = res.data["status"]
                
                # Оновлюємо статус реального користувача
                await asyncio.to_thread(
                    lambda: supabase.table("users").update({"status": status, "phone": phone}).eq("user_id", user_id).execute()
                )
                
                # Оновлюємо ліди (переносимо user_id з guest_id на user_id)
                await asyncio.to_thread(
                    lambda: supabase.table("leads").update({"user_id": user_id}).eq("user_id", guest_id).execute()
                )
                
                # Видаляємо гостьового користувача
                await asyncio.to_thread(
                    lambda: supabase.table("users").delete().eq("user_id", guest_id).execute()
                )
                
                return status
        except Exception as e:
            print(f"Помилка зв'язування гостьового акаунту в Supabase: {e}")
            
    return None
